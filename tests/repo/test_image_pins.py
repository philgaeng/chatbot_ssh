# SPDX-License-Identifier: Apache-2.0
"""
Container-image pin-drift pin (DPG-02).

**The finding this exists for.** `docker-compose.yml` pinned `redis:7` — the major only. Redis
relicensed at a *minor* bump: 7.2 was BSD-3-Clause, 7.4 went RSALv2/SSPLv1, neither OSI-approved.
The tag followed upstream onto that line and **nobody edited the file**. The licence moved
underneath us, and a dependency audit that reads manifests would never have seen it.

So the rule is not about Redis. **A floating tag is a licence you did not choose**, and the only
mechanical defence is to require enough of the version to make a relicence an opt-in event.

Two properties are pinned here:

1. Every image is pinned to at least MAJOR.MINOR, or is an explicitly justified exception below.
2. Compose and CI agree on the same image. If they drift, CI tests a different Redis than
   production runs, and a licence or behaviour finding in one is invisible in the other.

Spec: docs/sprints/2026-08-llm/01-licensing-and-governance-spec.md#dpg-02
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

MANIFESTS = (
    "docker-compose.yml",
    "docker-compose.grm.yml",
    ".github/workflows/ci.yml",
)

# Images we deliberately pin looser than MAJOR.MINOR, each with the reason it is safe.
#
# ⚠ This is a contract, not a suppression list. An entry here is a claim that the image's licence
# is stable across the range the tag spans. Adding a row means making that claim; if you cannot
# state the reason, pin the version instead.
ACCEPTED_LOOSE_PINS: dict[str, str] = {
    "postgres:15": (
        "PostgreSQL Licence (OSI-approved) has been stable for the life of the project and "
        "PostgreSQL has never relicensed. The major-only tag floats across patch releases, which "
        "is a reproducibility question rather than a licence one."
    ),
    "nginx:stable": (
        "BSD-2-Clause, unchanged since 2004. `stable` is nginx's own long-lived branch tag. "
        "Same trade as postgres:15 — floats for patches, no licence exposure."
    ),
}

IMAGE_RE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)


def _images() -> dict[str, list[str]]:
    """{image reference: [files it appears in]} across every manifest."""
    found: dict[str, list[str]] = {}
    for manifest in MANIFESTS:
        text = (REPO_ROOT / manifest).read_text(encoding="utf-8")
        for image in IMAGE_RE.findall(text):
            found.setdefault(image, []).append(manifest)
    return found


def _is_pinned(image: str) -> bool:
    """True if the tag carries at least MAJOR.MINOR, or is a digest."""
    if "@sha256:" in image:
        return True
    _, _, tag = image.rpartition(":")
    if not tag or "/" in tag:  # no tag at all — implicitly :latest
        return False
    return bool(re.match(r"^\d+\.\d+", tag))


def test_manifests_exist():
    for manifest in MANIFESTS:
        assert (REPO_ROOT / manifest).is_file(), f"{manifest} is missing"


def test_some_images_were_found():
    """A regex that silently matches nothing would make every assertion below vacuous."""
    assert len(_images()) >= 4, f"expected the stack's images, found {sorted(_images())}"


def test_every_image_is_pinned_or_explicitly_excepted():
    """Mutation check: change `redis:8.10` back to `redis:7` and this goes red."""
    offenders = [
        f"{image} (in {', '.join(files)})"
        for image, files in sorted(_images().items())
        if not _is_pinned(image) and image not in ACCEPTED_LOOSE_PINS
    ]
    assert not offenders, (
        "image(s) pinned too loosely — a floating tag is a licence you did not choose:\n  "
        + "\n  ".join(offenders)
        + "\n\nPin to MAJOR.MINOR, or add an entry to ACCEPTED_LOOSE_PINS stating why the "
        "licence is stable across the range the tag spans."
    )


def test_redis_is_pinned_to_a_minor():
    """The specific regression. Redis relicensed at a minor bump, so the major is not enough."""
    redis_images = [i for i in _images() if i.startswith("redis:")]
    assert redis_images, "no redis image found — has the service been renamed?"
    for image in redis_images:
        assert _is_pinned(image), (
            f"{image} is not pinned to MAJOR.MINOR. Redis 7.2 was BSD-3-Clause and 7.4 was "
            "RSALv2/SSPLv1; a major-only tag silently crosses that boundary."
        )
        assert image not in ACCEPTED_LOOSE_PINS, "redis must never be an accepted loose pin"


@pytest.mark.parametrize("name", ["redis", "postgres"])
def test_compose_and_ci_use_the_same_image(name):
    """Otherwise CI validates a different service than production runs.

    Both files declare these independently, which is exactly how they drift apart. The comment in
    docker-compose.yml says to bump them in lockstep; this is what makes that survive a hurried
    afternoon.
    """
    refs = {
        image
        for image in _images()
        if image.split(":")[0].split("/")[-1] == name
    }
    assert len(refs) == 1, (
        f"{name} is declared as {sorted(refs)} across {MANIFESTS} — they must match exactly, "
        "or CI tests a different image than the stack runs."
    )


def test_accepted_loose_pins_each_state_a_reason():
    """An exception without a stated reason is a suppression, and decays into cargo cult."""
    for image, reason in ACCEPTED_LOOSE_PINS.items():
        assert len(reason) > 60, f"{image}: give the actual licence-stability reason, not a note"


def test_accepted_loose_pins_are_still_in_use():
    """Remove an image from the stack and its exception should go too, not linger as fiction."""
    live = set(_images())
    stale = [image for image in ACCEPTED_LOOSE_PINS if image not in live]
    assert not stale, f"ACCEPTED_LOOSE_PINS lists image(s) no longer used: {stale}"
