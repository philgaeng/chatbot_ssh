#!/usr/bin/env python3
"""
Verify SMTP configuration: TCP reachability, login, optional test send.

Uses the same EmailClient transport as the Messaging API (port 465 = SMTPS).

Examples:
  # Inside backend container (recommended — same network as production sends):
  python scripts/ops/test_smtp.py --check-only
  python scripts/ops/test_smtp.py --send-to you@example.com

  # From repo root via Docker:
  scripts/ops/test-smtp.sh --check-only
  scripts/ops/test-smtp.sh --send-to you@example.com
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Find repo root whether run from scripts/ops/ or copied into a container."""
    for candidate in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents):
        if (candidate / "backend" / "services" / "messaging.py").is_file():
            return candidate
    return Path("/app")
REPO_ROOT = _repo_root()
sys.path.insert(0, str(REPO_ROOT))


def _load_env() -> str:
    from dotenv import load_dotenv

    for name in ("env.local", ".env"):
        path = REPO_ROOT / name
        if path.exists():
            load_dotenv(path, override=False)
            return name
    return "system"


def _probe_tcp(host: str, port: int, timeout: float) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "connected"
    except OSError as exc:
        return False, str(exc)


def _print_config() -> None:
    from backend.config.smtp_config import missing_smtp_env_fields, resolve_smtp_config, smtp_config_summary

    missing = missing_smtp_env_fields()
    if missing:
        print(f"FAIL: missing SMTP env: {', '.join(missing)}")
        sys.exit(1)

    cfg = resolve_smtp_config()
    if not cfg:
        print("FAIL: SMTP is not configured")
        sys.exit(1)

    summary = smtp_config_summary()
    transport = "ssl (SMTPS)" if cfg.port == 465 else "starttls"
    print("SMTP configuration:")
    print(f"  host:      {summary['host']}")
    print(f"  port:      {summary['port']} ({transport})")
    print(f"  username:  {summary['username']}")
    print(f"  from:      {summary['from_addr']} ({summary['from_display']})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Test GRM SMTP settings")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Connect and authenticate only (NOOP); do not send mail",
    )
    parser.add_argument(
        "--send-to",
        action="append",
        dest="send_to",
        metavar="EMAIL",
        help="Send a test email to this address (repeatable)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="TCP/SMTP timeout in seconds (default: 30)",
    )
    args = parser.parse_args()

    if args.check_only and args.send_to:
        parser.error("Use either --check-only or --send-to, not both")

    env_source = _load_env()
    print(f"Env source: {env_source if env_source != 'system' else os.environ.get('ENV_SOURCE', 'container/system')}")
    print()

    _print_config()

    from backend.config.smtp_config import resolve_smtp_config
    from backend.services.messaging import EmailClient

    cfg = resolve_smtp_config()
    assert cfg is not None

    print()
    print(f"Step 1/2: TCP probe {cfg.host}:{cfg.port} ...")
    ok, detail = _probe_tcp(cfg.host, cfg.port, args.timeout)
    if ok:
        print(f"  OK: {detail}")
    else:
        print(f"  FAIL: {detail}")
        print(
            "  Hint: the mail server may block this network (common from local WSL). "
            "Retry from the backend container on AWS/staging."
        )
        return 1

    print()
    step = "check-only (NOOP + login)" if args.check_only else "send test email"
    print(f"Step 2/2: SMTP {step} ...")
    client = EmailClient()
    if args.check_only:
        success = client.test_connection(check_only=True, timeout=int(args.timeout))
    else:
        recipients = args.send_to or []
        if not recipients:
            parser.error("Provide --send-to EMAIL or use --check-only")
        success = client.test_connection(send_to=recipients, timeout=int(args.timeout))

    if success:
        print("  OK: SMTP test passed")
        return 0

    print("  FAIL: SMTP test failed (see logs above)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
