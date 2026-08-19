# SPDX-License-Identifier: Apache-2.0

"""
The storage layer's three privacy defects — D-19 (F-2, F-3, F-4).

All three were found by DPG-04 reading the code to build a data-flow diagram, and none of them was
in any privacy spec — because every existing spec described the **architecture**, and none described
what the storage layer does when something goes wrong. That is where all three lived:

* **F-2** — `_encrypt_field` returned the **plaintext** when pgcrypto failed. The error was logged
  and the write proceeded, and `_decrypt_field` mirrored it, so reads came back correct and nothing
  downstream could tell. A deployment could store complainant PII in the clear and look healthy.
* **F-3** — the `*_hash` lookup tokens were a bare `sha256(value)`. Nepal's mobile space is a few
  tens of millions of candidates behind a fixed 97/98 prefix, so a phone hash was a reversible
  encoding, not a pseudonym — which makes those columns personal data.
* **F-4** — backups were written unencrypted by default; encryption happened only if an operator
  had set one of two variables. The contact columns stay ciphertext inside a dump, but the
  narrative, the officer notes and every voice recording and photograph do not.

⭐ **The clock, and why these are being fixed now:** no genuine grievance has been processed yet —
every record is seed or demo data. Today all three are ordinary engineering. After go-live each one
is a breach assessment.

Spec: docs/sprints/2026-08-llm/followups/storage-layer-privacy-defects.md
"""
from __future__ import annotations

import hashlib
import hmac
import inspect
from pathlib import Path

import pytest

from backend.services.database_services import base_manager as bm

REPO_ROOT = Path(__file__).resolve().parents[2]


class _Manager(bm.BaseDatabaseManager):
    """A manager that does not touch a database — only the crypto helpers are under test."""

    def __init__(self, key=None, fail=False):
        self.encryption_key = key
        self._fail = fail
        self.logger = __import__("logging").getLogger("test_storage_privacy")

    def execute_query(self, query, params=None, label=None):
        if self._fail:
            raise RuntimeError("pgcrypto unavailable")
        return [{"encrypted": "deadbeef"}]


# ── F-2 ──────────────────────────────────────────────────────────────────────

def test_encryption_failure_stops_the_write_instead_of_storing_plaintext():
    """
    ⭐ **F-2.** With a key configured, a pgcrypto failure must abandon the write. Returning the
    plaintext — the old behaviour — stores complainant PII in the clear and reports success.
    """
    manager = _Manager(key="a-key", fail=True)

    with pytest.raises(bm.EncryptionUnavailableError) as exc:
        manager._encrypt_field("9841234567")

    assert "9841234567" not in str(exc.value), "the error must not carry the value it failed to protect"


def test_a_successful_encryption_returns_ciphertext_not_the_input():
    manager = _Manager(key="a-key")
    assert manager._encrypt_field("9841234567") == "deadbeef"


def test_the_unencrypted_mode_still_works_but_says_so_once(caplog):
    """
    Dev runs without a key on purpose, so this path stays — but silence was the problem. It warns
    once per process: enough to be seen in a log, not so much that it becomes noise to filter out.
    """
    bm.BaseDatabaseManager._encryption_disabled_warned = False
    manager = _Manager(key=None)

    with caplog.at_level("WARNING"):
        assert manager._encrypt_field("9841234567") == "9841234567"
        manager._encrypt_field("another value")

    warnings = [r for r in caplog.records if "UNENCRYPTED" in r.getMessage()]
    assert len(warnings) == 1, "once per process — not never, and not per field"


def test_the_encryption_error_is_a_database_error_so_existing_handlers_see_it():
    assert issubclass(bm.EncryptionUnavailableError, bm.DatabaseError)


# ── F-3 ──────────────────────────────────────────────────────────────────────

def test_search_tokens_are_hmac_not_a_bare_hash(monkeypatch):
    """
    ⭐ **F-3.** The token must not be computable by anyone who knows the phone number — which, for
    a ten-digit space with a fixed prefix, is everyone.
    """
    monkeypatch.setenv("SEARCH_TOKEN_PEPPER", "pepper-value")
    manager = _Manager(key="a-key")
    phone = "+9779841234567"

    token = manager._hash_value(phone)

    assert token != hashlib.sha256(phone.encode()).hexdigest(), "this is the reversible form"
    assert token == hmac.new(b"pepper-value", phone.encode(), hashlib.sha256).hexdigest()


def test_the_token_is_stable_so_lookup_by_phone_still_works(monkeypatch):
    """The one property the schema needs: equal inputs, equal tokens."""
    monkeypatch.setenv("SEARCH_TOKEN_PEPPER", "pepper-value")
    manager = _Manager(key="a-key")

    assert manager._hash_value("+9779841234567") == manager._hash_value("+9779841234567")
    assert manager._hash_value("+9779841234567") != manager._hash_value("+9779841234568")


def test_a_different_pepper_gives_a_different_token(monkeypatch):
    """Which is what makes the token useless to someone who does not hold the secret."""
    manager = _Manager(key="a-key")
    monkeypatch.setenv("SEARCH_TOKEN_PEPPER", "one")
    first = manager._hash_value("+9779841234567")
    monkeypatch.setenv("SEARCH_TOKEN_PEPPER", "two")
    assert manager._hash_value("+9779841234567") != first


def test_the_pepper_falls_back_to_the_encryption_key(monkeypatch):
    """
    So an existing deployment gains the protection without a second secret to distribute. Not
    ideal — two uses of one secret — and better than leaving the tokens reversible.
    """
    monkeypatch.delenv("SEARCH_TOKEN_PEPPER", raising=False)
    manager = _Manager(key="the-encryption-key")

    assert manager._hash_value("x") == hmac.new(
        b"the-encryption-key", b"x", hashlib.sha256
    ).hexdigest()


def test_the_backfill_script_exists_and_never_writes_plaintext():
    """
    ⚠ Changing the algorithm invalidates every stored token, so lookups break until they are
    re-derived. A fix that silently breaks phone lookup would be traded for the defect it fixed.
    """
    script = REPO_ROOT / "scripts" / "database" / "rehash_search_tokens.py"
    assert script.exists(), "the tokens cannot be migrated without it"

    source = script.read_text()
    assert "--dry-run" in source
    assert "_decrypt_field" in source and "_hash_value" in source
    assert "print(plaintext" not in source and "print(f\"{plaintext" not in source


# ── F-4 ──────────────────────────────────────────────────────────────────────
#
# ⭐ These run the real `backup_db.sh` against a stubbed `docker`, and assert on what is left on
# disk afterwards. Source inspection would have been cheaper and would have proved nothing: the
# question is not whether the script mentions `BACKUP_ALLOW_UNENCRYPTED`, it is whether a plaintext
# dump survives the run.

BACKUP_SCRIPT = REPO_ROOT / "scripts" / "ops" / "backup_db.sh"

DOCKER_STUB = r"""#!/usr/bin/env bash
# Enough of docker to run the backup script with no daemon, no database and no volumes.
case "$1" in
  ps)     echo "stub_db" ;;
  exec)   echo "PGDMP-fake-dump-containing-a-grievance-narrative" ;;
  volume) echo "grms_uploads_data" ;;
  run)    # the script bind-mounts $BACKUP_DIR at /backup and tars into it
          for arg in "$@"; do
            case "$arg" in /backup/*) printf 'fake-voice-note' > "$STUB_BACKUP_DIR/${arg#/backup/}" ;; esac
          done ;;
esac
exit 0
"""


def _run_backup(tmp_path, **env):
    """Run the real script with a stub docker on PATH. Returns (returncode, stdout, files)."""
    import os
    import subprocess

    bindir = tmp_path / "bin"
    bindir.mkdir()
    stub = bindir / "docker"
    stub.write_text(DOCKER_STUB)
    stub.chmod(0o755)

    backup_dir = tmp_path / "backups"
    child = {
        **os.environ,
        "PATH": f"{bindir}:{os.environ['PATH']}",
        "BACKUP_DIR": str(backup_dir),
        "STUB_BACKUP_DIR": str(backup_dir),
        "GNUPGHOME": str(tmp_path / "gnupg"),
    }
    (tmp_path / "gnupg").mkdir(mode=0o700)
    for key in ("BACKUP_GPG_RECIPIENT", "BACKUP_PASSPHRASE", "BACKUP_ALLOW_UNENCRYPTED", "BACKUP_REMOTE"):
        child.pop(key, None)
    child.update({k: str(v) for k, v in env.items()})

    proc = subprocess.run(
        ["bash", str(BACKUP_SCRIPT), str(tmp_path)],
        env=child, capture_output=True, text=True, timeout=120,
    )
    files = sorted(f.name for f in backup_dir.iterdir()) if backup_dir.exists() else []
    return proc.returncode, proc.stdout + proc.stderr, files


def test_an_unencryptable_dump_is_discarded_not_left_on_disk(tmp_path):
    """
    ⭐ **F-4, the defect itself.** With neither variable set the old script wrote the dump and moved
    on. The contact columns stay ciphertext inside it, but the grievance narrative, every officer
    note, and — in the uploads tar — every voice recording and photograph do not.
    """
    code, out, files = _run_backup(tmp_path)

    assert not [f for f in files if f.endswith(".dump")], f"a plaintext dump survived: {files}"
    assert not [f for f in files if f.endswith(".tar.gz")], f"a plaintext uploads tar survived: {files}"
    assert code != 0, "and the run must report failure, so the ops monitor notices"
    assert "no backup kept" in out


def test_the_status_file_says_the_backup_failed_so_the_monitor_sees_it(tmp_path):
    """A discarded backup that reports success is worse than the defect — it hides the gap."""
    import json

    _run_backup(tmp_path)
    status = json.loads((tmp_path / "backups" / "last_backup.json").read_text())

    assert status["ok"] is False
    assert status["encrypted"] is False
    assert status["uploads_tar"] == ""


def test_an_operator_can_still_accept_the_risk_in_so_many_words(tmp_path):
    """
    The escape hatch stays: someone restoring a dev box has a real reason, and a rule with no
    override gets worked around with `cp`. It has to be deliberate, and it has to be logged.
    """
    code, out, files = _run_backup(tmp_path, BACKUP_ALLOW_UNENCRYPTED="1")

    assert [f for f in files if f.endswith(".dump")], f"the opt-in did not work: {files}"
    assert [f for f in files if f.endswith(".tar.gz")]
    assert code == 0
    assert "UNENCRYPTED" in out and "in the clear" in out


def test_a_passphrase_produces_an_encrypted_dump_and_removes_the_plaintext(tmp_path):
    """The path an operator is meant to take — and the plaintext must not linger beside the .gpg."""
    code, out, files = _run_backup(tmp_path, BACKUP_PASSPHRASE="a-test-passphrase")

    assert [f for f in files if f.endswith(".dump.gpg")], f"nothing was encrypted: {files}\n{out}"
    assert not [f for f in files if f.endswith(".dump")], "the plaintext was left behind"
    assert code == 0


def test_the_uploads_archive_is_encrypted_too_not_just_the_database(tmp_path):
    """
    It holds the voice notes and photographs — the most directly identifying material in the
    system, and none of it is encrypted at rest. It was never encrypted by this script at all.
    """
    _, out, files = _run_backup(tmp_path, BACKUP_PASSPHRASE="a-test-passphrase")

    assert [f for f in files if f.endswith(".tar.gz.gpg")], f"the uploads tar was not encrypted: {files}"
    assert not [f for f in files if f.endswith(".tar.gz")]


def test_an_encrypted_backup_is_not_deleted_by_the_prune_glob(tmp_path):
    """
    ⚠ Encryption renames the files, and a prune glob that no longer matches would hoard backups
    forever — a fix that quietly breaks retention. Both `.gpg` forms must still be reachable.
    """
    script = BACKUP_SCRIPT.read_text()
    prune = [line for line in script.splitlines() if line.startswith("find ")]

    assert any("app_db_*.dump.gpg" in line for line in prune)
    assert any("uploads_*.tar.gz*" in line for line in prune), "must match the .gpg form too"
