# SPDX-License-Identifier: Apache-2.0
"""
The nightly CVE scan must hand the database each finding once (GRM-113).

`ops.dependency_findings` is unique on `(source, package, advisory_id)` and a scan writes in one
transaction, so a repeated key rolls back the whole night. pip-audit repeats keys: the payload below
is the shape measured on the ops image 2026-09-15, where it lists an identical vulnerability twice
inside one dependency. The scan ran eleven nights on staging and saved nothing.

`ops/findings.py` is imported directly — no redis or SQLAlchemy — so this runs anywhere.
"""
from __future__ import annotations

from ops.findings import Finding, pip_audit_findings, unique_findings

ECDSA_VULN = {
    "id": "PYSEC-2026-1325",
    "fix_versions": [],
    "aliases": ["CVE-2024-23342", "GHSA-wj6h-64fc-37mp"],
    "description": "…",
}
DOTENV_VULN = {
    "id": "PYSEC-2026-2270",
    "fix_versions": ["1.2.2"],
    "aliases": ["GHSA-mf9w-mj56-hr94", "CVE-2026-28684"],
    "description": "…",
}
PAYLOAD = {
    "dependencies": [
        {"name": "ecdsa", "version": "0.19.2", "vulns": [ECDSA_VULN, dict(ECDSA_VULN)]},
        {"name": "python-dotenv", "version": "1.1.1", "vulns": [DOTENV_VULN, dict(DOTENV_VULN)]},
        {"name": "wheel", "version": "0.45.1", "vulns": [{"id": "CVE-2026-24049", "fix_versions": ["0.46.2"]}]},
        {"name": "httpx", "version": "0.28.1", "vulns": []},
        {"name": "skipped-editable", "skip_reason": "not on PyPI"},
    ]
}


def test_a_repeated_advisory_becomes_one_finding():
    findings = pip_audit_findings(PAYLOAD)

    keys = [f.key for f in findings]
    assert len(keys) == len(set(keys)), "a repeated key is what rolled back every night's scan"
    assert keys == [
        ("pip-audit", "ecdsa", "PYSEC-2026-1325"),
        ("pip-audit", "python-dotenv", "PYSEC-2026-2270"),
        ("pip-audit", "wheel", "CVE-2026-24049"),
    ]


def test_a_finding_keeps_what_the_report_shows():
    by_package = {f.package: f for f in pip_audit_findings(PAYLOAD)}

    assert by_package["python-dotenv"] == Finding(
        "pip-audit", "python-dotenv", "1.1.1", "PYSEC-2026-2270", "unknown", "1.2.2"
    )
    assert by_package["ecdsa"].fixed_in is None  # no fix released


def test_the_same_advisory_on_two_packages_is_two_findings():
    payload = {"dependencies": [
        {"name": "a", "version": "1", "vulns": [{"id": "X-1"}]},
        {"name": "b", "version": "1", "vulns": [{"id": "X-1"}]},
    ]}
    assert [f.package for f in pip_audit_findings(payload)] == ["a", "b"]


def test_a_list_payload_and_an_empty_one():
    assert [f.package for f in pip_audit_findings(PAYLOAD["dependencies"])] == ["ecdsa", "python-dotenv", "wheel"]
    assert pip_audit_findings({}) == []


def test_unique_findings_keeps_the_first_of_each_key():
    first = Finding("pip-licenses", "pkg", "1.0", "GPL-3.0", "high", None)
    again = Finding("pip-licenses", "pkg", "2.0", "GPL-3.0", "high", None)
    other = Finding("pip-licenses", "pkg", "1.0", "Unknown", "medium", None)
    assert unique_findings([first, again, other]) == [first, other]
