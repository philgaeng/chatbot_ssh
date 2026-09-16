# SPDX-License-Identifier: Apache-2.0

"""
Security monitoring (spec 12) — report-only, run by the ops scheduler.

- dependency_scan: pip-audit (primary) → upsert into ops.dependency_findings.
- licence_scan: pip-licenses → the same table. A *licence* check, not a vulnerability one
  (DPG-02 / Q-06). Indicator 2 of the Digital Public Goods Standard is a claim that has to stay
  true, and a one-off audit is stale the next time anybody adds a dependency — so it runs on the
  schedule beside the CVE scan rather than being a pre-submission artefact somebody remembers.
- pg_security_check: self-hosted substitute for Supabase Advisors.

Never auto-upgrades or blocks deploys. npm/Dependabot/Trivy sources are optional
extensions (see spec §2.1) and can be added behind env flags.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import subprocess

from sqlalchemy import text

from ops.checks import CRIT, OK, WARN, _emit
from ops.findings import Finding, pip_audit_findings, unique_findings
from ops.licences import classify_licence
from ops.db import session_scope
from ops.models import DependencyFinding

logger = logging.getLogger("ops.security")

# Where scripts/ops/npm_audit.sh drops its report (UI image / CI writes it).
NPM_AUDIT_JSON = os.environ.get("NPM_AUDIT_JSON", "/var/backups/grms/npm_audit.json")


def _upsert_finding(db, *, source, package, installed_ver, advisory_id, severity, fixed_in) -> None:
    row = (
        db.query(DependencyFinding)
        .filter_by(source=source, package=package, advisory_id=advisory_id)
        .one_or_none()
    )
    now = dt.datetime.now(dt.timezone.utc)
    if row:
        row.last_seen = now
        row.installed_ver = installed_ver
        row.severity = severity
        row.fixed_in = fixed_in
        row.resolved_at = None
    else:
        db.add(
            DependencyFinding(
                source=source,
                package=package,
                installed_ver=installed_ver,
                advisory_id=advisory_id,
                severity=severity,
                fixed_in=fixed_in,
            )
        )


def dependency_scan() -> None:
    """Run pip-audit against the installed env and upsert findings (report-only)."""
    try:
        proc = subprocess.run(
            ["pip-audit", "--format", "json", "--progress-spinner", "off"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        # pip-audit exits non-zero when vulns are found — that's expected.
        payload = json.loads(proc.stdout or "{}")
    except FileNotFoundError:
        _emit("dependency_scan", WARN, message="pip-audit not installed")
        return
    except Exception as exc:
        _emit("dependency_scan", WARN, message=f"pip-audit run failed: {exc}")
        return

    # Unique per key before any write: pip-audit repeats advisories, and one repeat used to roll
    # back the whole night (GRM-113, ops/findings.py).
    findings = pip_audit_findings(payload)
    seen_keys = {f.key for f in findings}
    counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "unknown": 0}
    try:
        with session_scope() as db:
            for f in findings:
                counts[f.severity if f.severity in counts else "unknown"] += 1
                _upsert_finding(db, **f._asdict())
            # Mark previously-open pip-audit findings that no longer appear as resolved.
            now = dt.datetime.now(dt.timezone.utc)
            open_rows = (
                db.query(DependencyFinding)
                .filter(DependencyFinding.source == "pip-audit", DependencyFinding.resolved_at.is_(None))
                .all()
            )
            for row in open_rows:
                if ("pip-audit", row.package, row.advisory_id) not in seen_keys:
                    row.resolved_at = now
    except Exception as exc:
        _emit("dependency_scan", WARN, message=f"persist failed: {exc}")
        return

    # Fold in npm audit findings if a report is available (written out-of-band).
    npm_counts = _ingest_npm_findings()

    total = sum(counts.values())
    merged = {k: counts.get(k, 0) + npm_counts.get(k, 0) for k in set(counts) | set(npm_counts)}
    status = CRIT if (merged.get("critical") or merged.get("high")) else (WARN if sum(merged.values()) else OK)
    _emit("dependency_scan", status, {"pip": counts, "npm": npm_counts, "total": sum(merged.values())})


def _ingest_npm_findings() -> dict:
    """Parse a saved `npm audit --json` (v7+) report and upsert source='npm'."""
    counts = {"critical": 0, "high": 0, "moderate": 0, "low": 0, "info": 0, "unknown": 0}
    if not os.path.exists(NPM_AUDIT_JSON):
        return {}
    try:
        with open(NPM_AUDIT_JSON) as fh:
            data = json.load(fh)
    except Exception as exc:
        logger.warning("npm audit json unreadable: %s", exc)
        return {}

    vulns = data.get("vulnerabilities", {}) or {}
    seen: set[tuple] = set()
    try:
        with session_scope() as db:
            for pkg, v in vulns.items():
                sev = (v.get("severity") or "unknown").lower()
                counts[sev if sev in counts else "unknown"] += 1
                advisory = None
                fixed = None
                for via in v.get("via", []) or []:
                    if isinstance(via, dict):
                        advisory = via.get("url") or (str(via.get("source")) if via.get("source") else None) or via.get("title")
                        break
                fa = v.get("fixAvailable")
                if isinstance(fa, dict):
                    fixed = fa.get("version")
                seen.add(("npm", pkg, advisory))
                _upsert_finding(
                    db,
                    source="npm",
                    package=pkg,
                    installed_ver=(v.get("range") or None),
                    advisory_id=advisory,
                    severity=sev,
                    fixed_in=fixed,
                )
            now = dt.datetime.now(dt.timezone.utc)
            for row in (
                db.query(DependencyFinding)
                .filter(DependencyFinding.source == "npm", DependencyFinding.resolved_at.is_(None))
                .all()
            ):
                if ("npm", row.package, row.advisory_id) not in seen:
                    row.resolved_at = now
    except Exception as exc:
        logger.warning("npm findings persist failed: %s", exc)
        return {}
    return {k: c for k, c in counts.items() if c}


# ── licence scan (DPG-02) ────────────────────────────────────────────────────────────────────
# The classification rules live in ops/licences.py — pure logic, no redis/SQLAlchemy imports, so
# they stay unit-testable without the ops stack installed (tests/repo/test_licence_scan.py).


def licence_scan() -> None:
    """Flag dependencies whose licence is unknown, non-OSI, or copyleft (report-only).

    Findings land in ops.dependency_findings with source='pip-licenses' and the licence string in
    advisory_id, so the existing resolve-on-disappearance logic works unchanged: fix a licence (or
    drop the package) and the row closes itself on the next run.
    """
    try:
        proc = subprocess.run(
            ["pip-licenses", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        # pip-licenses prints pip's own upgrade notice to stdout on some versions; start at the
        # first line that is exactly the opening bracket rather than at the first '[' character,
        # which would match "[notice]".
        lines = (proc.stdout or "").splitlines()
        start = next((i for i, line in enumerate(lines) if line.strip() == "["), None)
        payload = json.loads("\n".join(lines[start:])) if start is not None else []
    except FileNotFoundError:
        _emit("licence_scan", WARN, message="pip-licenses not installed")
        return
    except Exception as exc:
        _emit("licence_scan", WARN, message=f"pip-licenses run failed: {exc}")
        return

    flagged: list[Finding] = []
    for pkg in payload:
        licence = (pkg.get("License") or "").strip()
        severity, is_finding = classify_licence(licence)
        if is_finding:
            flagged.append(Finding("pip-licenses", pkg.get("Name") or "?", pkg.get("Version") or "",
                                   licence, severity, None))
    # The same table and key as the CVE scan, so the same guard: a repeat rolls back everything.
    findings = unique_findings(flagged)
    seen_keys = {f.key for f in findings}
    counts: dict[str, int] = {}
    try:
        with session_scope() as db:
            for f in findings:
                counts[f.severity] = counts.get(f.severity, 0) + 1
                _upsert_finding(db, **f._asdict())

            now = dt.datetime.now(dt.timezone.utc)
            open_rows = (
                db.query(DependencyFinding)
                .filter(
                    DependencyFinding.source == "pip-licenses",
                    DependencyFinding.resolved_at.is_(None),
                )
                .all()
            )
            for row in open_rows:
                if ("pip-licenses", row.package, row.advisory_id) not in seen_keys:
                    row.resolved_at = now
    except Exception as exc:
        _emit("licence_scan", WARN, message=f"persist failed: {exc}")
        return

    status = CRIT if counts.get("high") else (WARN if counts else OK)
    _emit("licence_scan", status, {"scanned": len(payload), "flagged": counts})


def pg_security_check() -> None:
    """Report-only Postgres posture checks (Advisors substitute). Read-only queries."""
    findings: list[str] = []
    try:
        with session_scope() as db:
            superusers = db.execute(text(
                "SELECT count(*) FROM pg_roles WHERE rolsuper AND rolcanlogin"
            )).scalar()
            if (superusers or 0) > 1:
                findings.append(f"{superusers} login-capable superusers")

            idle_txn = db.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE state = 'idle in transaction' "
                "AND xact_start < now() - interval '5 minutes'"
            )).scalar()
            if (idle_txn or 0) > 0:
                findings.append(f"{idle_txn} long idle-in-transaction sessions")

            long_running = db.execute(text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE state = 'active' AND query_start < now() - interval '5 minutes' "
                "AND query NOT ILIKE '%pg_stat_activity%'"
            )).scalar()
            if (long_running or 0) > 0:
                findings.append(f"{long_running} long-running queries (>5min)")
        status = WARN if findings else OK
        _emit("pg_security_check", status, {"findings": findings})
    except Exception as exc:
        _emit("pg_security_check", OK, message=f"skipped ({exc})")
