"""
The benchmark set is data, so nothing in the language stops it drifting. This does.

DPG-20 committed ``tests/data/benchmark/`` as the reproducibility artefact for indicator 4, and
three of its acceptance criteria are the kind that decay silently:

  * **every item is above ``MIN_CLASSIFY_CHARS``** — an item under the floor is never sent to a
    model at all (DPG-19), so it measures the gate and quietly deflates every accuracy number;
  * **categories are drawn from the live taxonomy, not invented** — a label that no longer exists
    scores as a miss against every candidate, which reads exactly like a model problem;
  * **PII spans resolve** — they are stored as substrings precisely so this test can prove they do.

The pins below read the **live** registry and the **live** taxonomy, never a copy. A test that
restated either would be the failure mode ``tests/ticketing/test_boundary_policy.py`` was rewritten
to remove: two mirrors that agree with each other and with nothing else.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-20
Data: tests/data/benchmark/README.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from backend.config.llm_config import get_llm_settings, is_too_short_to_process

BENCHMARK_DIR = Path(__file__).resolve().parents[2] / "tests" / "data" / "benchmark"
GENERAL = BENCHMARK_DIR / "general_classification.jsonl"
GATE = BENCHMARK_DIR / "gate_fixtures.jsonl"
README = BENCHMARK_DIR / "README.md"

VALID_SCRIPTS = {"devanagari", "roman_nepali", "english", "code_mixed"}
VALID_ORIGINS = {"typed", "voice"}
VALID_PII_TYPES = {"person_name", "phone", "address"}
# The KL Road districts, per ticketing/seed/mock_tickets.py. Widen this deliberately, never by
# accident: a district outside the project's scope is a benchmark item measuring nothing real.
VALID_DISTRICTS = {"Jhapa", "Morang", "Sunsari"}


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def general() -> list[dict]:
    return _load(GENERAL)


@pytest.fixture(scope="module")
def gate() -> list[dict]:
    return _load(GATE)


@pytest.fixture(scope="module")
def live_categories() -> set[str]:
    """The taxonomy as the running system holds it — DB when seeded, CSV otherwise."""
    from backend.config.constants import LIST_OF_CATEGORIES

    assert LIST_OF_CATEGORIES, "the live taxonomy is empty; the benchmark cannot be graded against it"
    return set(LIST_OF_CATEGORIES)


# ── The floor (DPG-19) ───────────────────────────────────────────────────────


def test_every_benchmark_item_is_above_the_classification_floor(general):
    """
    Below MIN_CLASSIFY_CHARS no model is called, so a short item measures the gate, not the model.

    ⚠ This asserts through ``is_too_short_to_process`` rather than against the number 25, so it
    keeps holding if the floor moves — which it is designed to do, per language (llm_config.py).
    """
    floor = get_llm_settings().min_classify_chars
    short = [(d["id"], len(d["text"].strip())) for d in general if is_too_short_to_process(d["text"])]
    assert not short, (
        f"benchmark items below the {floor}-character floor would be skipped, not classified: {short}. "
        "Short text belongs in gate_fixtures.jsonl, which exists so nobody 'fixes' it into the set."
    )


def test_gate_fixtures_pin_the_gate_in_both_directions(gate):
    """The fixtures are only worth committing if they actually straddle the floor."""
    for item in gate:
        assert is_too_short_to_process(item["text"]) is item["expect_skipped"], (
            f"{item['id']}: expect_skipped={item['expect_skipped']} but the gate disagrees. "
            f"stripped length={len(item['text'].strip())}, floor={get_llm_settings().min_classify_chars}"
        )
    assert any(i["expect_skipped"] for i in gate), "no fixture below the floor — the gate is untested"
    assert any(not i["expect_skipped"] for i in gate), "no fixture above the floor — only half a pin"


def test_the_gate_counts_stripped_length_not_non_whitespace_characters(gate):
    """
    ``llm_config.py`` and ``.env.open`` both said *"non-whitespace characters"*. They were wrong:
    the code is ``len(text.strip())``, so internal spaces count. ``gate-06`` is the difference —
    25 characters, 13 of them non-whitespace, and it is **not** skipped.

    Both comments were corrected in the commit that added this file. This test is what stops the
    wrong wording coming back, because the two readings only diverge on a spaced-out string.
    """
    item = next(i for i in gate if i["id"] == "gate-06")
    stripped = len(item["text"].strip())
    non_whitespace = len("".join(item["text"].split()))
    floor = get_llm_settings().min_classify_chars

    assert non_whitespace < floor <= stripped, "gate-06 no longer straddles the two readings"
    assert not is_too_short_to_process(item["text"]), (
        "the gate counted non-whitespace characters. If that is now deliberate, the README §5 and "
        "the llm_config.py comment must change with it — they currently document stripped length."
    )


# ── The labels ───────────────────────────────────────────────────────────────


def test_every_label_exists_in_the_live_taxonomy(general, live_categories):
    """Gold and acceptable labels alike. An invented label scores as a miss against every model."""
    unknown = {
        (d["id"], c)
        for d in general
        for c in d["categories"] + d["categories_acceptable"]
        if c not in live_categories
    }
    assert not unknown, (
        f"labels not in the live taxonomy: {sorted(unknown)}. "
        "Categories come from backend/dev-resources/lookup_tables/list_category.txt, never from prose."
    )


def test_every_item_has_a_gold_label_and_no_overlap_with_the_acceptable_set(general):
    for d in general:
        assert d["categories"], f"{d['id']} has no gold category"
        overlap = set(d["categories"]) & set(d["categories_acceptable"])
        assert not overlap, (
            f"{d['id']}: {sorted(overlap)} is both gold and merely-acceptable. "
            "Acceptable means 'neither rewarded nor penalised' — a label cannot be both."
        )


def test_multi_label_items_are_tagged_as_such(general):
    """
    Set-level scoring is a DPG-23 acceptance criterion, and it only earns its keep if the set
    actually contains multi-label items. This pins that they exist and are findable.
    """
    multi = [d for d in general if len(d["categories"]) > 1]
    assert len(multi) >= 5, f"only {len(multi)} multi-label items; set-level scoring measures nothing"
    for d in multi:
        assert "multi_label" in d["edge"], f"{d['id']} has two gold labels but is not tagged multi_label"


# ── PII (serves DPG-35) ──────────────────────────────────────────────────────


def test_every_pii_span_resolves_to_exactly_one_occurrence(general):
    """
    Spans are substrings, not offsets, so that this test can derive offsets by search and an
    ambiguous span fails the build instead of producing a silently wrong offset (README §4.4).
    """
    for d in general:
        for span in d["pii"]:
            assert span["type"] in VALID_PII_TYPES, f"{d['id']}: unknown PII type {span['type']!r}"
            occurrences = d["text"].count(span["text"])
            assert occurrences == 1, (
                f"{d['id']}: PII span {span['text']!r} occurs {occurrences} times, not once. "
                "A span that appears twice has no single offset; one that appears zero times is stale."
            )


def test_the_hard_pii_cases_are_present(general):
    """
    These three are the reason the set is authored rather than sampled — they are rare in real
    traffic and they are exactly what DPG-35 must not miss. Losing one to an edit would be silent.
    """
    tagged = {tag for d in general for tag in d["edge"]}
    for required in ("devanagari_digits", "third_party_name", "code_switching", "mixed_digits"):
        assert required in tagged, f"no item tagged {required!r} — see README §2"

    devanagari_digits = re.compile(r"[०-९]")
    numeric_pii = [
        span["text"]
        for d in general
        for span in d["pii"]
        if span["type"] == "phone"
    ]
    assert any(devanagari_digits.search(p) for p in numeric_pii), (
        "no phone number written in Devanagari digits. A redactor matching r'\\d' passes without one, "
        "and then fails in production on the script most complainants actually use."
    )


# ── Shape ────────────────────────────────────────────────────────────────────


def test_item_shape_is_uniform(general):
    ids = [d["id"] for d in general]
    assert len(ids) == len(set(ids)), "duplicate ids"
    for d in general:
        assert d["script"] in VALID_SCRIPTS, f"{d['id']}: script {d['script']!r}"
        assert d["origin"] in VALID_ORIGINS, f"{d['id']}: origin {d['origin']!r}"
        assert d["district"] in VALID_DISTRICTS, f"{d['id']}: district {d['district']!r}"
        assert isinstance(d["high_priority"], bool), f"{d['id']}: high_priority is not a bool"
        assert isinstance(d["sensitive"], bool), f"{d['id']}: sensitive is not a bool"
        assert d["note"] != "" or d["edge"] == [], f"{d['id']}: an edge-case item with no note"


def test_no_committed_item_is_marked_sensitive(general):
    """
    §1 of the README, and the owner's decision of 2026-08-19: harassment and abuse narratives are
    never committed. An item marked ``sensitive`` here would mean that decision had been reversed
    in a data file rather than in a document.
    """
    flagged = [d["id"] for d in general if d["sensitive"]]
    assert not flagged, (
        f"{flagged} is marked sensitive in a committed file. The SEAH slice is held by the project "
        "owner and never enters this repository — docs/models/01_seah_detection_benchmark.md §3.3."
    )


def test_the_seah_confusable_negatives_are_present(general):
    """
    The committed set carries the **false-alarm** half of the SEAH measurement. Without these a
    recall-only benchmark recommends a model that flags everything (method doc §1).
    """
    confusable = [d for d in general if "seah_confusable" in d["edge"]]
    assert len(confusable) >= 5, f"only {len(confusable)} confusable negatives"
    assert all(not d["sensitive"] for d in confusable), "a confusable negative must not be gold-positive"


# ── The document and the data agree ──────────────────────────────────────────


def test_readme_states_the_actual_sizes(general, gate):
    """
    Rule: a benchmark table with a stale cell is worse than none. The README quotes counts, so the
    counts are pinned — the same chain CLAUDE.md's boundary table uses (doc ↔ test ↔ data).
    """
    text = README.read_text(encoding="utf-8")
    assert f"| **{len(general)}** |" in text, (
        f"README does not state {len(general)} general items; update §1 and §7 together"
    )
    assert f"| **{len(gate)}** |" in text, f"README does not state {len(gate)} gate fixtures"

    shortest = min(len(d["text"].strip()) for d in general)
    assert f"the shortest is {shortest} characters" in text, (
        f"README §5 quotes a stale shortest-item length; it is now {shortest}"
    )


def test_readme_records_the_uncovered_taxonomy_category(general, live_categories):
    """
    23 of 24 categories are covered; the SEAH one is empty on purpose. If that ever changes — in
    either direction — the README's explanation must change with it, because it is the sentence a
    reviewer will read to understand why a category is missing.
    """
    covered = {c for d in general for c in d["categories"]}
    uncovered = live_categories - covered
    assert uncovered == {"Gender - Gender Discrimination And Harrassment"}, (
        f"coverage changed: {sorted(uncovered)} uncovered. Update README §1, which explains why "
        "exactly one category is empty and what the committed set carries in its place."
    )


@pytest.mark.integration
def test_no_benchmark_text_came_out_of_the_database():
    """
    "No production PII in any committed file — **verified, not assumed**" (DPG-20 acceptance).

    Provenance is a claim about how the file was written and no test can check that. What a test
    *can* check is the thing that would make the claim false in the obvious way: that no committed
    item is a copy of a row in the grievance table. It runs against the seeded CI database.
    """
    import psycopg2

    from backend.config.constants import DB_CONFIG

    texts = {d["text"] for d in _load(GENERAL)}
    with psycopg2.connect(
        host=DB_CONFIG["host"],
        database=DB_CONFIG["database"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        port=DB_CONFIG["port"],
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT grievance_description FROM public.grievances WHERE grievance_description IS NOT NULL")
            stored = {row[0] for row in cur.fetchall()}

    collisions = texts & stored
    assert not collisions, (
        f"{len(collisions)} benchmark items are byte-identical to stored grievances. The committed "
        "set is authored synthetic data and must never be lifted from the database."
    )


# ── Severity, and the defect that made this pin necessary ────────────────────


def _authored_high_priority() -> dict[str, bool]:
    """
    The taxonomy's **authored** high-priority flag, read as the last field of each CSV row.

    ⚠ Deliberately not read through ``CLASSIFICATION_DATA``, and that is the whole point of this
    helper. Five rows of ``grievances_categorization_v1.1.csv`` carry more (or fewer) columns than
    the header declares — a third follow-up-question pair that the header never named — so
    ``csv.DictReader`` puts the surplus under the ``None`` key and ``row["high_priority"]`` picks up
    a **question string** instead of ``True``. ``"…scale from 1 to 5?".lower() == "true"`` is
    ``False``, so four categories silently lost their high-priority flag, among them
    ``Environmental - Air Pollution`` (the dust complaint, demo scenario 1) and
    ``Gender - Gender Discrimination And Harrassment`` (the SEAH route).

    The benchmark records the **authored** value, so it is already correct when the loader is fixed.
    Logged as a deviation and a follow-up: docs/sprints/2026-08-llm/followups/taxonomy-csv-column-drift-silently-clears-high-priority.md
    """
    import csv

    from backend.config.constants import DEFAULT_CSV_PATH

    authored: dict[str, bool] = {}
    with open(DEFAULT_CSV_PATH, encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    for row in rows[1:]:
        if not row:
            continue
        key = f"{row[4].replace('-', ' ').title()} - {row[0].replace('-', ' ').title()}"
        authored[key] = row[-1].strip().lower() == "true"
    return authored


def test_benchmark_severity_follows_the_authored_taxonomy(general):
    """
    ``high_priority`` in this set is the taxonomy's value, never the author's intuition — which is
    what "categories drawn from the live taxonomy, not invented" means for the severity label too.
    """
    authored = _authored_high_priority()
    wrong = [
        (d["id"], category, d["high_priority"], authored[category])
        for d in general
        for category in d["categories"]
        if category in authored and len(d["categories"]) == 1 and d["high_priority"] != authored[category]
    ]
    assert not wrong, (
        f"benchmark severity disagrees with the taxonomy: {wrong} (item, category, benchmark, taxonomy)"
    )


def test_the_taxonomy_parse_defect_is_still_present_and_still_logged():
    """
    A canary, not an endorsement. It asserts the *known* extent of the defect so that fixing it
    fails this test loudly — at which point delete this test and close the follow-up, rather than
    discovering months later that the fix landed and nobody updated the record.
    """
    from backend.config.constants import CLASSIFICATION_DATA

    authored = _authored_high_priority()
    disagreements = {
        category
        for category, value in authored.items()
        if category in CLASSIFICATION_DATA and CLASSIFICATION_DATA[category]["high_priority"] != value
    }
    expected = {
        "Wildlife, Environmental - Wildlife Destruction",
        "Environmental - Air Pollution",
        "Environmental, Social - Cutting Of Trees",
        "Gender - Gender Discrimination And Harrassment",
    }
    assert disagreements == expected, (
        f"the taxonomy parse defect changed shape: now {sorted(disagreements)}, was {sorted(expected)}. "
        "If it was fixed, delete this test and close "
        "docs/sprints/2026-08-llm/followups/taxonomy-csv-column-drift-silently-clears-high-priority.md"
    )
