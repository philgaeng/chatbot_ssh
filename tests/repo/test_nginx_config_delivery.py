# SPDX-License-Identifier: Apache-2.0
"""
`GRM-103` / `GRM-067` — how the staging nginx config reaches the container, and what it says.

**GRM-103, the delivery defect.** The site config was a SINGLE-FILE bind mount. `git pull` updates a
file by writing a new inode and renaming it, and a single-file mount stays pinned to the OLD inode —
so after every deploy the container served the pre-pull config, `nginx -s reload` re-read the stale
copy and reported success, and even `nginx -t` validated the stale copy. nginx was also never in
`AWS_DEPLOY_SERVICES`, so no deploy touched it. Measured on staging 2026-09-14 (host sha `a206acb2`,
container sha `89e923b4`): that is how GRM-014's rate limiting sat merged-but-inert for a week.

**GRM-067, the content drift.** Staging lacked production's security headers, advertised its nginx
version, added `Access-Control-Allow-Origin *` to every response — duplicating the correct values
Keycloak and the API set themselves, which browsers reject — and, through a compose MERGE, loaded the
WSL site config and published port 8080 as well.

⚠ **These are text checks on purpose.** `docker compose config` would be more faithful, but it needs
the Docker CLI and an `env.local`, and a guard that only runs where those happen to exist is a guard
that silently stops running. The behaviour itself was verified on the staging host, beside the live
nginx: config valid, no conflicting server names, headers correct per location, and a git-style
replace followed by a reload served the new config.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AWS_COMPOSE = REPO_ROOT / "docker-compose.aws.yml"
AWS_CONF = REPO_ROOT / "deployment" / "nginx" / "webchat_rest_compose_aws.conf"
BOOTSTRAP = REPO_ROOT / "deployment" / "nginx" / "bootstrap.sh"


def _service_block(compose_text: str, name: str) -> str:
    """The text of one top-level service, up to the next one."""
    m = re.search(rf"^  {name}:\n(.*?)(?=^  [a-z_][a-z0-9_-]*:\n|\Z)", compose_text, re.M | re.S)
    assert m, f"service {name!r} not found in compose file"
    return m.group(1)


def _block(conf: str, opener: str | int) -> str:
    """The body of an nginx block, brace-matched.

    ⚠ `opener` may be a POSITION, not only text. Given text, `str.index` returns the FIRST match —
    and the first `server {` in this file is the port-80 block. The TLS fixture passed the text
    `"server {"` and so read the wrong block, which made the no-site-wide-CORS check pass vacuously
    (port 80 never had CORS). Caught by the header checks failing, not by review.
    """
    start = opener if isinstance(opener, int) else conf.index(opener)
    depth, i = 0, conf.index("{", start)
    for j in range(i, len(conf)):
        if conf[j] == "{":
            depth += 1
        elif conf[j] == "}":
            depth -= 1
            if depth == 0:
                return conf[i + 1 : j]
    raise AssertionError(f"unbalanced block after {opener!r}")


def _active(text: str) -> str:
    """Drop comment lines, so a directive quoted in a comment cannot satisfy a check."""
    return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))


@pytest.fixture(scope="module")
def nginx_service() -> str:
    return _service_block(AWS_COMPOSE.read_text(encoding="utf-8"), "nginx")


@pytest.fixture(scope="module")
def tls_server() -> str:
    conf = AWS_CONF.read_text(encoding="utf-8")
    m = re.search(r"server\s*\{[^{}]*listen 443", conf)
    assert m, "no TLS server block in the staging conf"
    body = _block(conf, m.start())
    assert "listen 443" in body, "the TLS fixture resolved to a block that does not listen on 443"
    return body


# ── GRM-103: delivery ─────────────────────────────────────────────────────────


def test_the_site_config_directory_is_mounted_not_a_single_file(nginx_service: str) -> None:
    """⭐ The regression itself. A single-file mount cannot follow `git pull`'s rename."""
    body = _active(nginx_service)
    assert "./deployment/nginx:/etc/nginx/site:ro" in body, "the deployment/nginx DIRECTORY must be mounted"
    single = re.findall(r"\./deployment/nginx/[^:\s]+\.conf:", body)
    assert not single, f"a site config is bind-mounted as a single file again: {single}"


def test_volumes_and_ports_REPLACE_the_base_lists_rather_than_merge(nginx_service: str) -> None:
    """Without `!override` compose merges with docker-compose.yml — which is how staging came to load
    the WSL config and publish 0.0.0.0:8080. Production's file already used it for volumes."""
    assert re.search(r"^\s+volumes: !override\s*$", nginx_service, re.M), "nginx volumes must be !override"
    assert re.search(r"^\s+ports: !override\s*$", nginx_service, re.M), "nginx ports must be !override"


def test_the_wsl_site_config_is_not_mounted_on_staging(nginx_service: str) -> None:
    assert "webchat_rest_compose_wsl.conf" not in _active(nginx_service)


def test_staging_publishes_only_80_and_443(nginx_service: str) -> None:
    ports_section = re.search(r"ports: !override\n(.*?)(?=^\s+[a-z_]+:)", nginx_service, re.M | re.S)
    assert ports_section, "could not read the ports list"
    published = re.findall(r'-\s*"?([0-9]+):[0-9]+"?', _active(ports_section.group(1)))
    assert sorted(published) == ["443", "80"], f"staging nginx should publish exactly 80 and 443, got {published}"


def test_nginx_starts_through_bootstrap_which_includes_from_the_mounted_directory(nginx_service: str) -> None:
    assert "sh /etc/nginx/site/bootstrap.sh" in _active(nginx_service)
    assert re.search(r"NGINX_SITE_CONF:\s*webchat_rest_compose_aws\.conf", nginx_service)
    script = _active(BOOTSTRAP.read_text(encoding="utf-8"))
    assert 'site="/etc/nginx/site/${NGINX_SITE_CONF' in script, "bootstrap must resolve the site from the mount"
    assert "include %s" in script, "bootstrap must `include` the site, not copy or mount it"
    assert "--test" in script and "nginx -t" in script, "bootstrap must offer the validation mode the deploy uses"


def test_aws_deploys_validate_then_apply_then_reload_nginx() -> None:
    """⚠ Validation must happen in a throwaway container BEFORE the running one is touched, and never
    as `exec nginx -t` in the running container — which is exactly what passed an untested config."""
    for target in ("aws-deploy", "aws-deploy-full"):
        out = subprocess.run(
            ["make", "-n", target, "IMAGE_TAG=abc1234"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout
        assert out.strip(), f"make -n {target} produced nothing"
        v = out.index("bootstrap.sh --test")
        a = out.index("up -d --no-deps nginx")
        r = out.index("nginx -s reload")
        assert v < a < r, f"{target}: expected validate < apply < reload"
        # And BEFORE the port verification, so a deploy never reports OK over a failed apply.
        assert 'ui_port="' in out, f"{target}: port verification step not found — the check itself is broken"
        assert r < out.index('ui_port="'), f"{target}: nginx must be applied before the ports are verified"


def test_the_nginx_deploy_step_contains_no_single_quote() -> None:
    """The whole remote command travels inside '...' over SSH; one stray single quote in the macro
    splits it silently. The registry-login step survived that only because its quoted text happened
    to contain no spaces."""
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    body = re.search(r"^define REMOTE_APPLY_NGINX\n(.*?)^endef", text, re.M | re.S)
    assert body, "REMOTE_APPLY_NGINX not found"
    assert "'" not in body.group(1)


# ── GRM-067: content ──────────────────────────────────────────────────────────


def test_no_site_wide_cors_is_added(tls_server: str) -> None:
    """⭐ It duplicated the correct values Keycloak and the API send (`grm-auth…, *` and `*, *`,
    measured), and browsers reject two ACAO values. Our own pages are same-origin."""
    top = re.sub(r"location[^{]*\{(?:[^{}]|\{[^{}]*\})*\}", "", _active(tls_server))
    assert "Access-Control-Allow-Origin" not in top, "a server-level CORS header is back"
    assert "Access-Control-Allow-Origin *" not in _active(AWS_CONF.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "directive",
    [
        "server_tokens off;",
        'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;',
        'add_header X-Content-Type-Options "nosniff" always;',
        'add_header X-Frame-Options "SAMEORIGIN" always;',
        'add_header Referrer-Policy "strict-origin-when-cross-origin" always;',
    ],
)
def test_staging_carries_productions_security_headers(tls_server: str, directive: str) -> None:
    assert directive in _active(tls_server), f"staging TLS server is missing prod's `{directive}`"


def test_keycloak_does_not_inherit_the_server_level_headers() -> None:
    """Keycloak sends a complete, STRICTER set (Referrer-Policy no-referrer, CSP frame-ancestors).
    Inheriting ours appends `strict-origin-when-cross-origin`, and browsers honour the LAST value —
    silently weakening the login pages. Any `add_header` in the location stops inheritance."""
    keycloak = _active(_block(AWS_CONF.read_text(encoding="utf-8"), "location /keycloak/"))
    assert "add_header" in keycloak, "/keycloak/ must declare its own add_header to stop inheritance"
    for strict in ("Referrer-Policy", "X-Frame-Options", "Strict-Transport-Security"):
        assert strict not in keycloak, f"/keycloak/ must leave {strict} to Keycloak"
    assert "add_header_inherit" not in keycloak, (
        "add_header_inherit is unknown to nginx 1.28 (the local nginx:stable) and nginx refuses to start"
    )


def test_message_keeps_its_explicit_origin() -> None:
    """The orchestrator adds no CORS headers, so /message is the one place nginx still must."""
    message = _active(_block(AWS_CONF.read_text(encoding="utf-8"), "location /message"))
    assert "add_header Access-Control-Allow-Origin https://nepal-gms-chatbot.facets-ai.com;" in message
