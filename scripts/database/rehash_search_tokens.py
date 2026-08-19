#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

"""
Re-derive the `*_hash` search tokens after D-19/F-3 changed how they are computed.

**Why this exists.** The tokens were a bare `sha256(value)`. For this data that is a reversible
encoding rather than a pseudonym: Nepal's mobile space is a few tens of millions of candidates with
a fixed 97/98 prefix, so a `complainant_phone_hash` could be turned back into a phone number with a
laptop and a loop. They are now `HMAC-SHA256(pepper, value)`, which keeps the equality lookup the
schema needs and makes the token useless without the secret.

⚠ **Every existing token is therefore stale**: lookups by phone, email, name or address will not
match until this has run. It decrypts each encrypted column with the application's own key, re-hashes
the plaintext, and writes the new token back — no plaintext is ever stored or printed.

Run it in the container, as everything else here is run:

    docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
      exec backend python scripts/database/rehash_search_tokens.py --dry-run
    …then without --dry-run.

⚠ Requires `DB_ENCRYPTION_KEY` (to decrypt) and, if you set one, `SEARCH_TOKEN_PEPPER`. With neither
configured there is nothing to do: unencrypted deployments do not hash.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.services.database_services.postgres_services import db_manager  # noqa: E402

# table → (id column, [(encrypted column, hash column)])
TARGETS = {
    "complainants": (
        "complainant_id",
        [
            ("complainant_phone", "complainant_phone_hash"),
            ("complainant_email", "complainant_email_hash"),
            ("complainant_full_name", "complainant_full_name_hash"),
            ("complainant_address", "complainant_address_hash"),
        ],
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = parser.parse_args()

    if not db_manager.encryption_key:
        print("DB_ENCRYPTION_KEY is not set — this deployment stores no hashed tokens. Nothing to do.")
        return 0

    total, changed, failed = 0, 0, 0
    for table, (id_column, columns) in TARGETS.items():
        existing = {c for _, c in columns}
        rows = db_manager.execute_query(
            f"SELECT {id_column}, "
            + ", ".join(f"{src}, {dst}" for src, dst in columns)
            + f" FROM public.{table}",
            (),
            "rehash_scan",
        ) or []

        for row in rows:
            total += 1
            updates = {}
            for src, dst in columns:
                ciphertext = row.get(src)
                if not ciphertext:
                    continue
                try:
                    plaintext = db_manager._decrypt_field(ciphertext)
                except Exception as exc:                       # pragma: no cover - operational
                    print(f"  ! {row[id_column]}: cannot decrypt {src} ({type(exc).__name__})")
                    failed += 1
                    continue
                if not plaintext or plaintext == ciphertext:
                    # Undecryptable, or the row predates encryption. Re-hashing a ciphertext would
                    # write a token that matches nothing — skip it rather than corrupt the column.
                    continue
                token = db_manager._hash_value(plaintext)
                if token != row.get(dst):
                    updates[dst] = token

            if updates:
                changed += 1
                if args.dry_run:
                    print(f"  would update {row[id_column]}: {sorted(updates)}")
                else:
                    assignments = ", ".join(f"{col} = %s" for col in updates)
                    db_manager.execute_query(
                        f"UPDATE public.{table} SET {assignments} WHERE {id_column} = %s",
                        (*updates.values(), row[id_column]),
                        "rehash_update",
                    )

    verb = "would change" if args.dry_run else "changed"
    print(f"scanned {total} row(s); {verb} {changed}; {failed} undecryptable")
    if failed:
        print("⚠ Undecryptable rows keep their old tokens and will not match a lookup. Investigate "
              "before assuming the backfill is complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
