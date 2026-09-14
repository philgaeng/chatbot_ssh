# SPDX-License-Identifier: Apache-2.0
"""
Every remote deploy command reaches the host as ONE single-quoted word.

The deploy targets run `ssh <host> '<macros>'`. The macros expand in the LOCAL Makefile, so the
whole remote script travels inside one pair of single quotes, and **a single quote anywhere in a
macro ends that quoting early.** What follows it is parsed by the local shell, not the remote one.

⚠ Measured 2026-09-14, and it failed three different ways, none of them loud until the last:

- `'{{index .Image}}'` and `printf '  %-18s %s  %s\\n'` fell outside the quotes, split on their
  spaces, and reached the host as a different command. The "running images" report every deploy
  prints read `%s  %sn  ticketing_api  ghcr.io/…app:5984ccd` — **no digest, for every deploy,**
  while its comment says the digest "is the only answer to: is the running container the commit I
  asked for".
- `'$MIG_IMG'` fell outside the quotes, so the LOCAL shell expanded it to nothing: the error meant
  to name the missing image named none.
- The apostrophe in "the checkout's code" left an odd count, the local shell met `(GRM-099)`
  unquoted, and `make aws-deploy` stopped with `Syntax error: "(" unexpected` — before `ssh` ran,
  so on the first deploy after `GRM-099` merged, **no AWS deploy target could run at all.**

Its per-macro tests were green: `make -n` prints a command, it never parses one. This file does.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

SSH_TARGETS = [
    "aws-deploy",
    "aws-deploy-light",
    "aws-deploy-full",
    "aws-deploy-ops",
    "aws-seed-seah-providers",
    "prod-deploy",
    "prod-deploy-light",
    "prod-deploy-full",
    "prod-deploy-ops",
    "prod-seed-seah-providers",
]


def _ssh_line(target: str) -> str:
    out = subprocess.run(
        ["make", "-n", target, "IMAGE_TAG=abc1234"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout
    lines = [l for l in out.splitlines() if l.startswith("ssh ")]
    assert len(lines) == 1, f"{target}: expected exactly one ssh command, found {len(lines)}"
    return lines[0]


def _payload(line: str) -> str:
    head, sep, rest = line.partition(" '")
    assert sep and rest.endswith("'"), "the remote command must be passed as one '...' argument"
    return rest[:-1]


def test_every_ssh_target_is_listed() -> None:
    """A new ssh-wrapped target that is not in SSH_TARGETS would be checked by nothing."""
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    found = set()
    current = None
    for line in text.splitlines():
        if line and not line[0].isspace() and ":" in line and not line.startswith(("#", "define")):
            current = line.split(":", 1)[0].strip()
        elif line.startswith("\t$(SSH_") and " '" in line and current:
            found.add(current)
    assert found == set(SSH_TARGETS), f"ssh-wrapped targets changed: {sorted(found ^ set(SSH_TARGETS))}"


@pytest.mark.parametrize("target", SSH_TARGETS)
def test_the_remote_command_contains_no_single_quote(target: str) -> None:
    """⭐ The invariant. Any `'` inside the payload is a place where quoting ends."""
    payload = _payload(_ssh_line(target))
    i = payload.find("'")
    assert i == -1, (
        f"{target}: a single quote inside the remote command ends the ssh quoting early — "
        f"use double quotes, or rephrase: …{payload[max(0, i - 60):i + 40]}…"
    )


@pytest.mark.parametrize("target", SSH_TARGETS)
def test_both_shells_can_parse_it(target: str) -> None:
    """The LOCAL shell parses the whole line; the REMOTE shell parses the payload. `sh -n` reads
    without executing, and `sh` is dash on the CI runner and on the host, as it is for make."""
    line = _ssh_line(target)
    local = subprocess.run(["sh", "-n", "-c", line], capture_output=True, text=True)
    assert local.returncode == 0, f"{target}: the local shell rejects the command: {local.stderr.strip()}"
    remote = subprocess.run(["sh", "-n", "-c", _payload(line)], capture_output=True, text=True)
    assert remote.returncode == 0, f"{target}: the remote shell would reject it: {remote.stderr.strip()}"
