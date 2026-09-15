# SPDX-License-Identifier: Apache-2.0

"""
Scanner output → dependency findings, one per key (GRM-113).

Pure logic, in its own module for the reason `ops/licences.py` gives: `ops/security.py` imports
redis, SQLAlchemy and the ops models, so a test reaching this through it could only run where the
full ops stack is installed — see `tests/repo/test_dependency_findings.py`.

**Why a finding must be unique before it reaches the database.** `ops.dependency_findings` has one
row per `(source, package, advisory_id)` (`uq_dep_finding`), and a scan writes every finding in one
transaction. The ops session does not autoflush, so the upsert's lookup cannot see a row added
earlier in the same run: a repeated key is inserted twice, the constraint refuses the second, and
**the whole night's findings are rolled back.** pip-audit does repeat them — measured 2026-09-15, it
lists an identical vulnerability twice inside one dependency (`ecdsa`, `python-dotenv`, `sanic-cors`,
`setuptools`). The scan had run eleven nights on staging and saved nothing.
"""
from __future__ import annotations

from typing import Iterable, NamedTuple, Optional


class Finding(NamedTuple):
    source: str
    package: str
    installed_ver: Optional[str]
    advisory_id: Optional[str]
    severity: str
    fixed_in: Optional[str]

    @property
    def key(self) -> tuple[str, str, Optional[str]]:
        return (self.source, self.package, self.advisory_id)


def unique_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Keep the first finding for each `(source, package, advisory_id)`, in order."""
    seen: set[tuple[str, str, Optional[str]]] = set()
    out: list[Finding] = []
    for f in findings:
        if f.key not in seen:
            seen.add(f.key)
            out.append(f)
    return out


def pip_audit_findings(payload: dict | list) -> list[Finding]:
    """Findings from `pip-audit --format json`, one per package and advisory."""
    deps = payload.get("dependencies", []) if isinstance(payload, dict) else payload
    return unique_findings(
        Finding(
            source="pip-audit",
            package=dep.get("name"),
            installed_ver=dep.get("version"),
            advisory_id=v.get("id"),
            severity=(v.get("severity") or "unknown").lower(),
            fixed_in=",".join(v.get("fix_versions", []) or []) or None,
        )
        for dep in deps
        for v in dep.get("vulns", []) or []
    )
