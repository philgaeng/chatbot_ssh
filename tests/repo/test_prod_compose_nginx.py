# SPDX-License-Identifier: Apache-2.0
"""
`GRM-147` — production's nginx must be a coherent merge of TWO overlays, not of one.

**Measured 2026-09-16, by taking the production site down.** Production runs
`docker-compose.yml` + `aws.yml` + `grm.yml` + `prod.yml`, in that order, so `prod.yml` sits on top
of `aws.yml` and inherits every key it does not restate.

`GRM-103` (2026-09-14) changed `aws.yml`'s nginx to mount the `deployment/nginx` **directory** at
`/etc/nginx/site` and to start via `sh /etc/nginx/site/bootstrap.sh`, which includes whichever file
`NGINX_SITE_CONF` names. `prod.yml` was not touched: it still overrode `volumes` with a single-file
mount. Merged, production got `aws.yml`'s command and `aws.yml`'s `NGINX_SITE_CONF`, but
`prod.yml`'s volumes. Rendering the exact four-file merge showed:

    command         : sh /etc/nginx/site/bootstrap.sh
    NGINX_SITE_CONF : webchat_rest_compose_aws.conf     <- staging's server_name
    /etc/nginx/site mounted? False

So `bootstrap.sh` was absent, nginx could not start, and it crash-looped until rolled back.

⭐ **The crash is what saved production.** Had the script been found, nginx would have loaded
`webchat_rest_compose_aws.conf` — staging's hostname — and served it on `grm-chatbot.dor.gov.np`.

**Why no test caught it:** each file was valid on its own. `aws.yml` was correct for staging;
`prod.yml` was correct for the layout it was written against. The defect existed only in the
merge, and nothing checked the merge. These tests check the merge's invariants **statically** —
no Docker — so they run in CI rather than skipping there, which would make them decoration.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
NGINX_DIR = REPO_ROOT / "deployment" / "nginx"
SITE_MOUNT = "/etc/nginx/site"


class _ComposeLoader(yaml.SafeLoader):
    """Compose's `!override` / `!reset` tags are not YAML — read the value beneath them."""


def _passthrough(loader: yaml.SafeLoader, node: yaml.Node):
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)


for _tag in ("!override", "!reset"):
    _ComposeLoader.add_constructor(_tag, _passthrough)


def _nginx(name: str) -> dict:
    data = yaml.load((REPO_ROOT / name).read_text(encoding="utf-8"), Loader=_ComposeLoader)
    return (data.get("services") or {}).get("nginx") or {}


def _command_text(svc: dict) -> str:
    cmd = svc.get("command")
    return " ".join(cmd) if isinstance(cmd, list) else (cmd or "")


def _volume_targets(svc: dict) -> list[str]:
    targets = []
    for v in svc.get("volumes") or []:
        if isinstance(v, str):
            parts = v.split(":")
            if len(parts) >= 2:
                targets.append(parts[1])
        elif isinstance(v, dict):
            targets.append(v.get("target", ""))
    return targets


AWS = _nginx("docker-compose.aws.yml")
PROD = _nginx("docker-compose.prod.yml")


def test_prod_mounts_the_directory_the_inherited_start_command_needs() -> None:
    """⭐ The crash. If `aws.yml` starts nginx from `/etc/nginx/site`, and `prod.yml` overrides the
    volumes, then `prod.yml` must mount `/etc/nginx/site` itself — it does not inherit the mount."""
    if SITE_MOUNT not in _command_text(AWS) and not PROD.get("command"):
        pytest.skip("aws.yml no longer starts nginx from /etc/nginx/site")
    effective_command = _command_text(PROD) or _command_text(AWS)
    if SITE_MOUNT in effective_command:
        assert SITE_MOUNT in _volume_targets(PROD), (
            f"production's nginx starts with `{effective_command}` but prod.yml's volumes do not "
            f"mount {SITE_MOUNT}. prod.yml overrides volumes, so it does NOT inherit aws.yml's "
            "mount: nginx will not find bootstrap.sh and will crash-loop (GRM-147)."
        )


def test_prod_names_its_own_site_config_not_stagings() -> None:
    """⭐ The near-miss. `NGINX_SITE_CONF` is an environment key, so `prod.yml` inherits
    `aws.yml`'s value unless it restates it — and `aws.yml`'s is staging's hostname."""
    prod_conf = (PROD.get("environment") or {}).get("NGINX_SITE_CONF")
    aws_conf = (AWS.get("environment") or {}).get("NGINX_SITE_CONF")
    assert prod_conf, (
        f"prod.yml sets no NGINX_SITE_CONF, so production inherits aws.yml's `{aws_conf}` and "
        "would serve staging's server_name on the production hostname (GRM-147 / GRM-141)."
    )
    assert prod_conf != aws_conf, f"prod.yml and aws.yml name the same site config: {prod_conf}"
    assert "prod" in prod_conf, f"production's NGINX_SITE_CONF does not look like a prod config: {prod_conf}"


def test_the_named_site_config_exists_where_bootstrap_will_look() -> None:
    """`bootstrap.sh` exits if `/etc/nginx/site/$NGINX_SITE_CONF` is missing — so the name must
    resolve to a real file under `deployment/nginx`, the directory mounted there."""
    prod_conf = (PROD.get("environment") or {}).get("NGINX_SITE_CONF")
    assert prod_conf and (NGINX_DIR / prod_conf).is_file(), (
        f"NGINX_SITE_CONF={prod_conf!r} is not a file in deployment/nginx"
    )


def test_prod_keeps_the_certificates_mounted() -> None:
    """The prod config names `/etc/letsencrypt/live/...`; dropping that mount fails `nginx -t`."""
    assert "/etc/letsencrypt" in _volume_targets(PROD), (
        "prod.yml's nginx volumes no longer mount /etc/letsencrypt — the TLS config cannot load"
    )


def _prod_ssh_targets() -> list[str]:
    """Every `prod-*` target whose recipe sends a command over ssh."""
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    found, current = [], None
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line and not line.startswith(("#", "define", "\t")):
            current = line.split(":", 1)[0].strip()
        elif line.startswith("\t$(SSH_PROD)") and current and current.startswith("prod-"):
            if current not in found:
                found.append(current)
    return found


@pytest.mark.parametrize("target", _prod_ssh_targets())
def test_every_prod_target_sends_the_production_overlay(target: str) -> None:
    """`GRM-141` — production runs FOUR compose files; `REMOTE_COMPOSE` names three.

    ⚠ **Measured 2026-09-16 by taking the site down.** `aws.yml` sets
    `NGINX_SITE_CONF=webchat_rest_compose_aws.conf` — *staging's* server_name — and its volume set
    carries no certbot mounts. `prod.yml` restores both and must come last so its
    `volumes: !override` wins. A prod target that omits it points production's nginx at staging's
    hostname and drops the TLS certificates.

    Each `prod-*` target overrides `REMOTE_COMPOSE` with `PROD_REMOTE_COMPOSE` via a
    target-specific variable. That is one line per target and therefore one line to forget, which
    is what this test is for: a new prod target added without it would inherit the staging overlay
    and look entirely normal until it reloaded nginx.
    """
    out = subprocess.run(
        ["make", "-n", target, "IMAGE_TAG=abc1234"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout

    # ⚠ Asserting `"docker-compose.prod.yml" in out` is NOT enough, and the first version of this
    # test did exactly that and passed against a deliberately broken Makefile. `prod-deploy` also
    # calls REMOTE_VERIFY_GRM_PORTS_PROD, which names prod.yml independently — so the string is
    # present whether or not the DEPLOY commands carry it. Count instead: every compose invocation
    # in the payload must have its own `-f docker-compose.prod.yml`.
    invocations = out.count("docker compose --env-file env.local")
    with_prod = out.count("-f docker-compose.prod.yml")
    assert invocations > 0, f"{target}: found no compose invocation to check — did the macro move?"
    assert with_prod == invocations, (
        f"{target}: {invocations} compose invocation(s) but only {with_prod} carry "
        "docker-compose.prod.yml. The ones without it use the STAGING overlay — staging's "
        "server_name and no certbot mounts (GRM-141). Add "
        f"`{target}: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)` above its recipe."
    )
