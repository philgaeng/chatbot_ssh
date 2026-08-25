# SPDX-License-Identifier: Apache-2.0

"""
Resolve a category value onto the live taxonomy — or refuse to guess (D-51).

**Why this exists.** The classifier is told to reply with keys of the category dictionary and
mostly does. When it does not, the shape of the miss is remarkably consistent: measured over the
105-item benchmark, every unresolvable value was a **correct leaf under a wrong or missing
parent** — `Wildlife Passage` (the classification half dropped), `Road Hazard - Noise Pollution`
(a real leaf filed under the wrong family). Nothing downstream tolerates that: an off-catalogue
value is stored, shown to the complainant, synced to ticketing, and then matches no filter, no
report and no `high_priority` lookup. It is invisible precisely because it *looks* fine.

**Why a leaf index and not a second model call.** Category keys are `Classification - Leaf`, and
the leaves are unique, so the repair is a dictionary lookup: deterministic, free, offline-testable,
and it cannot invent a mapping. A repair prompt could — and it would also silence the signal:
eighteen items asking for a `Road Hazard` family is how the taxonomy gap was found (§7 of
`docs/dpg/model-benchmarks.md`), and a model quietly folding them into `Environmental - Air
Pollution` would have buried it.

⚠ **Ambiguity is never resolved by guessing.** A leaf reachable from two classifications is
dropped from the index, so a value that only matches it is reported unresolvable rather than
assigned to whichever came first. Same for a value that names only a classification.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

_SEPARATOR = " - "
_WHITESPACE = re.compile(r"\s+")


def fold_category_key(raw: Any) -> str:
    """
    Fold a reply into the key form `load_classification_data` builds — casing and hyphens only.

    ⚠ Split on `" - "` **first**: several names carry a hyphen of their own
    (`Gender-Based Access Issues`), and a blanket replace would eat the separator with them.
    This is the fold the benchmark scores with (`scripts/ops/llm_benchmark.py`), kept here so the
    product and its measurement cannot drift apart on what "the same category" means.
    """
    text = str(raw or "").strip().strip("\"'")
    if _SEPARATOR not in text:
        return _WHITESPACE.sub(" ", text.replace("-", " ").title()).strip()
    classification, _, name = text.partition(_SEPARATOR)
    folded = f"{classification.replace('-', ' ').title()}{_SEPARATOR}{name.replace('-', ' ').title()}"
    return _WHITESPACE.sub(" ", folded).strip()


def _match_key(value: str) -> str:
    """Comparison form: fold, then casefold. Never used for storage — only for lookup."""
    return fold_category_key(value).casefold()


def build_leaf_index(catalogue: Iterable[str]) -> dict[str, str]:
    """
    Map each *unambiguous* leaf to its canonical key.

    A leaf claimed by two classifications is removed entirely rather than resolved to one of them:
    an administrator is free to add `Safety - Dust` next to `Road Hazard - Dust`, and on that day
    a bare `Dust` stops being answerable. Dropping it is the honest outcome.
    """
    index: dict[str, str] = {}
    ambiguous: set[str] = set()
    for key in catalogue:
        if not key or _SEPARATOR not in str(key):
            continue
        leaf = _match_key(str(key).partition(_SEPARATOR)[2])
        if not leaf:
            continue
        if leaf in index and index[leaf] != key:
            ambiguous.add(leaf)
        index[leaf] = str(key)
    for leaf in ambiguous:
        index.pop(leaf, None)
    return index


@dataclass
class CategoryResolution:
    """What resolution did, kept separable so callers can log the repair and the loss apart."""

    kept: list[str] = field(default_factory=list)
    repaired: list[tuple[str, str]] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.repaired or self.dropped)


def resolve_categories(
    values: Iterable[Any],
    catalogue: Iterable[str] | Mapping[str, Any],
    *,
    exclude: Iterable[str] = (),
) -> CategoryResolution:
    """
    Fold each value onto a canonical key, repair what the leaf index can, drop the rest.

    Three tiers, strongest first: the value already is a key; it folds to one (casing, hyphens);
    its leaf identifies exactly one. Anything else is `dropped` — reported, never stored.

    `exclude` removes values already chosen elsewhere, which is what keeps a repaired alternative
    from duplicating a primary category it just resolved onto.
    """
    keys = list(catalogue.keys() if isinstance(catalogue, Mapping) else catalogue)
    canonical = {_match_key(key): key for key in keys}
    leaves = build_leaf_index(keys)
    seen = {_match_key(value) for value in exclude if str(value or "").strip()}

    resolution = CategoryResolution()
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue
        match = _match_key(raw)
        resolved = canonical.get(match) or leaves.get(match)
        if resolved is None and _SEPARATOR in raw:
            # The parent was wrong, not the answer: `Road Hazard - Noise Pollution` is
            # `Environmental - Noise Pollution` said by a model that mis-filed it.
            resolved = leaves.get(_match_key(raw.partition(_SEPARATOR)[2]))
        if resolved is None:
            resolution.dropped.append(raw)
            continue
        if _match_key(resolved) in seen:
            continue
        seen.add(_match_key(resolved))
        resolution.kept.append(resolved)
        if resolved != raw:
            resolution.repaired.append((raw, resolved))
    return resolution
