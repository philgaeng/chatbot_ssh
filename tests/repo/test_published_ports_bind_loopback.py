# SPDX-License-Identifier: Apache-2.0
"""
`GRM-151` — a published port with no interface binds **every** interface, and Docker publishes
ahead of the host firewall.

**Measured on the DOR production host, 2026-09-17.** `docker-compose.grm.yml` published four ports
with no interface: Keycloak's admin console, **Postgres**, `ticketing_api` and `grm_ui`. On that
host — whose own address is on the DOR internal network, behind a NAT — that made the database and
the IdP admin console reachable by anything on that network or on the VPN.

⚠ **`ufw` does not cover this.** `15_host_hardening.md` §1 says so in its own note: Docker inserts
its rules ahead of the host firewall, so the binding is the control, not the firewall. The DOR host
has no ufw installed at all, which made the point moot there and urgent everywhere else.

⭐ **The pattern already existed in the same file.** `backend` and `orchestrator` were already
`127.0.0.1:...`. Four services simply had not followed it, and nothing checked. That is this test.

**What loopback still serves**, so the binding costs nothing real: nginx reaches these services over
the container network, not the host port; `docker compose port` still reports them (so the deploy's
port verification still matches `*":3001"`); and an SSH tunnel terminates on the host, which is how
a GUI database client should connect anyway.

`HOST_BIND` exists so a host that genuinely needs to publish outward sets `HOST_BIND=0.0.0.0`
deliberately, rather than getting it by omission.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.grm.yml",
    "docker-compose.aws.yml",
    "docker-compose.prod.yml",
]

# A published port entry: `- "<something>:<container port>"`.
PORT_LINE = re.compile(r'^\s*-\s*"(?P<spec>[^"]+)"\s*$')

# An explicit host interface: an IP, or a ${VAR} that resolves to one, before the ports.
HAS_INTERFACE = re.compile(r'^(\d{1,3}(\.\d{1,3}){3}|\$\{HOST_BIND[^}]*\}):')

# ⭐ The only ports that SHOULD face outward, and why. nginx is the web server: publishing is its
# entire job, and TLS certificates are issued against these. Everything else reaches it through
# the container network.
OUTWARD_ALLOWED = {
    "80:80",
    "443:443",
    "${NGINX_HOST_PORT:-8080}:80",
}


def _published_ports() -> list[tuple[str, int, str]]:
    found = []
    for name in COMPOSE_FILES:
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        in_ports = False
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("ports:"):
                in_ports = True
                continue
            m = PORT_LINE.match(line)
            if in_ports and m:
                found.append((name, n, m.group("spec")))
                continue
            if stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                in_ports = False
    return found


PUBLISHED = _published_ports()


def test_the_scan_found_something() -> None:
    """If this file stops finding ports, the test below passes vacuously."""
    assert PUBLISHED, "no published ports found — the compose layout moved and this test is inert"


@pytest.mark.parametrize("name,line,spec", PUBLISHED, ids=[f"{n}:{l}" for n, l, _ in PUBLISHED])
def test_every_published_port_binds_an_interface(name: str, line: int, spec: str) -> None:
    if spec in OUTWARD_ALLOWED:
        return
    assert HAS_INTERFACE.match(spec), (
        f"{name}:{line} publishes `{spec}` with no host interface, so it binds 0.0.0.0 — every "
        "interface the host has. On a deployed host that means the LAN and any VPN, and Docker "
        "publishes ahead of ufw so a host firewall will not cover it (GRM-151).\n"
        "Fix: prefix with ${HOST_BIND:-127.0.0.1}: — or, if it genuinely must face outward, add it "
        "to OUTWARD_ALLOWED here with the reason."
    )
