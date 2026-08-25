"""
The scoring rules, pinned — because every one of them is a way to publish a wrong number.

DPG-23's acceptance names three of these explicitly (score set-level, score sensitive detection on
recall, price it before building it) and each has a failure mode that looks like a model result:

  * grading raw category strings against canonical keys deflates every score by the width of the
    mismatch, and reads as a model that cannot follow the taxonomy;
  * single-label accuracy marks a correct multi-label answer wrong;
  * counting a defensible alternate as a false positive punishes exactly the behaviour the
    `grievance_categories_alternative` list exists to produce;
  * a null recall rendered as 0.0 says the model missed everything, when the truth is that the
    committed set has no positives to miss.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-23
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ops import llm_benchmark as bench


def _item(item_id: str, predicted, gold, acceptable=(), latency=1.0) -> bench.ItemResult:
    return bench.ItemResult(
        item_id=item_id, ok=True, latency_s=latency,
        predicted=list(predicted), gold=list(gold), acceptable=list(acceptable),
    )


def _scores(items) -> bench.Scores:
    return bench.Scores(model="m", task="classify", items=list(items))


# ── Normalisation (README §4.1) ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected",
    [
        # The prompt shows the model raw CSV values; the benchmark labels are canonical keys.
        ("Relocation issues - Poor housing quality of the resettlement site",
         "Relocation Issues - Poor Housing Quality Of The Resettlement Site"),
        # ⭐ The case a blanket replace destroys: a hyphen INSIDE the name, and the " - " separator.
        ("Gender, Social - Gender-Based Access Issues", "Gender, Social - Gender Based Access Issues"),
        # Already canonical — must be idempotent, or a second pass corrupts it.
        ("Environmental - Air Pollution", "Environmental - Air Pollution"),
        # Models quote things.
        ('"Safety - Road Safety Provisions"', "Safety - Road Safety Provisions"),
        ("  Environmental - Noise Pollution  ", "Environmental - Noise Pollution"),
    ],
)
def test_category_strings_fold_to_the_canonical_key(raw, expected):
    assert bench.canonical_category(raw) == expected


def test_normalisation_is_idempotent():
    """Applied twice must equal applied once, or a re-score silently changes the answer."""
    for raw in ("Gender, Social - Gender-Based Access Issues", "Relocation issues - Forced relocation issues"):
        once = bench.canonical_category(raw)
        assert bench.canonical_category(once) == once


def test_every_gold_label_in_the_committed_set_survives_normalisation():
    """
    ⭐ The end-to-end pin. If the fold ever stops producing labels the set actually uses, every
    candidate scores near zero and it looks like a Nepali-quality problem.
    """
    import json

    items = [json.loads(line) for line in bench.GENERAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    for item in items:
        for category in item["categories"]:
            assert bench.canonical_category(category) == category, (
                f"{item['id']}: gold label {category!r} is not a fixed point of the normaliser"
            )


# ── Set-level scoring ────────────────────────────────────────────────────────


def test_a_correct_multi_label_answer_scores_as_correct():
    """Single-label accuracy would mark this wrong. Eight items in the set carry two gold labels."""
    scores = _scores([_item("a", ["X - A", "Y - B"], ["X - A", "Y - B"])])
    result = scores.set_level()

    assert result["f1"] == 1.0
    assert result["exact_set_accuracy"] == 1.0
    # ⚠ Assert the credit COUNT, not only the ratio. The first version of this test asserted the
    # ratios alone and survived a scorer truncated to one label per item — because with
    # predicted == gold every reduced form still scores 1.0. A test that a mutation cannot kill is
    # decorative (D-42), and this is the assertion that kills it.
    assert result["tp"] == 2, "both gold labels must be credited, not just the first"


def test_a_partially_correct_set_is_partially_credited():
    scores = _scores([_item("a", ["X - A"], ["X - A", "Y - B"])])
    result = scores.set_level()

    assert result["tp"] == 1 and result["fn"] == 1 and result["fp"] == 0
    assert result["exact_set_accuracy"] == 0.0, "a subset is not an exact match"


def test_an_acceptable_alternate_is_neither_rewarded_nor_penalised():
    """
    ⭐ The rule that keeps the metric honest. The system returns categories AND alternatives, so a
    defensible neighbour is the feature working. Counting it as a false positive would rank models
    by how narrowly they answer.
    """
    scores = _scores([_item("a", ["X - A", "Z - C"], ["X - A"], acceptable=["Z - C"])])
    result = scores.set_level()

    assert result["fp"] == 0, "an acceptable alternate was counted as a false positive"
    assert result["tp"] == 1
    assert result["exact_set_accuracy"] == 1.0
    assert result["precision"] == 1.0, "and it must not dilute precision either"


def test_an_invented_category_is_a_false_positive():
    """
    Not hypothetical: measured 2026-08-20, `gpt-5-nano` returned `Road Hazard - Dust` — a category
    that exists nowhere in the taxonomy — on every dust item in the first sample, despite the prompt
    saying *"Do not create new categories"*. Production logs these and stores them anyway.
    """
    scores = _scores([_item("a", ["Environmental - Air Pollution", "Road Hazard - Dust"],
                            ["Environmental - Air Pollution"])])
    result = scores.set_level()

    assert result["fp"] == 1
    assert result["precision"] == 0.5
    assert result["exact_set_accuracy"] == 0.0


def test_blocked_items_are_excluded_from_every_score():
    """A 402 must not enter the numerator or the denominator. It measures the account."""
    blocked = bench.ItemResult("b", ok=False, blocked=True, error="Error code: 402 - credits depleted")
    scores = _scores([_item("a", ["X - A"], ["X - A"]), blocked])

    assert scores.set_level()["n"] == 1, "a blocked item was scored"
    assert len(scores.blocked) == 1


# ── Sensitive detection ──────────────────────────────────────────────────────


def _detection(pairs) -> bench.Scores:
    items = [
        bench.ItemResult(f"i{n}", ok=True, expected_sensitive=expected, detected_sensitive=detected)
        for n, (expected, detected) in enumerate(pairs)
    ]
    return bench.Scores(model="m", task="detect", items=items)


def test_detection_reports_a_confusion_matrix_not_one_number():
    """A miss is a safeguarding failure; a false alarm makes an ordinary complaint disappear into a
    channel most officers cannot see. One number hides that the costs differ."""
    result = _detection([(True, True), (True, False), (False, True), (False, False)]).detection()

    assert (result["tp"], result["fn"], result["fp"], result["tn"]) == (1, 1, 1, 1)
    assert result["recall"] == 0.5
    assert result["false_alarm_rate"] == 0.5


def test_recall_over_a_set_with_no_positives_is_not_measured_rather_than_zero():
    """
    ⭐ The committed set is exactly this shape — false-alarm controls only, because the harassment
    narratives are held by the owner and never enter this repository. A `0.0` here would say the
    model missed everything.
    """
    result = _detection([(False, False), (False, True)]).detection()

    assert result["recall"] is None, "a null recall must not become 0.0"
    assert "Not measured" in result["recall_note"]
    assert result["false_alarm_rate"] == 0.5, "the half the committed set CAN measure still reports"


def test_the_committed_set_declares_no_positive_scenarios():
    """Pins §0.2 from the scoring side: if a positive ever appears here, the split has been broken."""
    import json

    items = [json.loads(line) for line in bench.GENERAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert not [i["id"] for i in items if i.get("sensitive")]


# ── Latency, against a budget that is a knob ────────────────────────────────


def test_latency_reports_the_fraction_over_each_budget_not_just_a_percentile():
    """
    The owner made the 30 s budget a knob on 2026-08-20 — raisable to 45 s or 60 s with the cost
    stated. A recommendation to raise it is only actionable with the fraction of complainants who
    would wait that long, so all three are reported.
    """
    scores = _scores([_item(f"i{n}", [], [], latency=latency)
                      for n, latency in enumerate([5, 10, 20, 35, 50, 70])])
    result = scores.latency()

    # abs=1e-4 because the harness rounds to 4 places on purpose — a fraction printed to fifteen
    # significant figures reads as a precision the sample size does not have.
    assert result["over_30s"] == pytest.approx(3 / 6, abs=1e-4)
    assert result["over_45s"] == pytest.approx(2 / 6, abs=1e-4)
    assert result["over_60s"] == pytest.approx(1 / 6, abs=1e-4)
    assert result["max"] == 70


def test_latency_over_an_empty_run_says_not_measured():
    assert "Not measured" in bench.Scores(model="m", task="classify").latency()["note"]


# ── The SEAH set may never live in this repository ──────────────────────────


def test_a_seah_set_inside_the_repository_is_refused(capsys):
    """
    ⚠ The one hard refusal. A path inside the repo means somebody is about to commit harassment
    narratives — the thing the owner decided on 2026-08-19 must never happen, because *"three
    hundred realistic Nepali harassment complaints sitting in it will be read as leaked case data
    by somebody, regardless of how the file is labelled"*.
    """
    inside = bench.REPO_ROOT / "tests" / "data" / "benchmark" / "seah.jsonl"

    assert bench._refuse_in_repo_seah_set(inside) == 2
    assert "REFUSING" in capsys.readouterr().err


def test_main_actually_refuses_before_it_loads_anything(monkeypatch, capsys):
    """
    ⚠ **The wiring, not just the helper.** The test above passed against a build where `main()` had
    the guard removed entirely — it exercised the refusal function while nothing called it. A guard
    nothing invokes is the same defect as a marker nothing runs, and on this particular guard the
    cost of missing it is committed harassment narratives.

    Also asserts it refuses **before** reading the file: the path need not exist.
    """
    inside = bench.REPO_ROOT / "tests" / "data" / "benchmark" / "does-not-exist-seah.jsonl"
    monkeypatch.setattr(
        "sys.argv", ["llm_benchmark", "--seah-set", str(inside), "--estimate"]
    )

    assert bench.main() == 2, "main() did not refuse an in-repo SEAH path"
    assert "REFUSING" in capsys.readouterr().err


def test_an_out_of_repo_seah_path_is_not_refused_by_the_same_check():
    outside = Path("/var/tmp/held-out-seah.jsonl")
    assert not outside.resolve().is_relative_to(bench.REPO_ROOT)


# ── Cost ─────────────────────────────────────────────────────────────────────


def test_the_estimate_prices_the_real_prompt_including_the_duplicated_catalogue():
    """
    ⚠ Cost here scales with the TAXONOMY, not the grievance: the classification prompt injects the
    24-category catalogue twice, in two shapes (measured at 20,725 characters, D-30). An estimate
    built from grievance length alone is wrong by more than an order of magnitude.
    """
    import json

    items = [json.loads(line) for line in bench.GENERAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()][:10]
    data = bench.estimate(items, ["m"], ["classify"])

    grievance_chars = sum(len(i["text"]) for i in items)
    assert data["per_run"]["prompt_tokens"] > grievance_chars, (
        "the estimate ignored the catalogue — it must dominate"
    )
    assert data["caveats"], "an estimate without its caveats is a number people quote"


def test_the_meter_reports_reasoning_share_because_it_is_invisible_and_dominant():
    meter = bench.UsageMeter()
    meter.calls, meter.prompt_tokens, meter.completion_tokens, meter.reasoning_tokens = 1, 1000, 1000, 900

    data = meter.as_dict(items=100, price_in=1.0, price_out=2.0)

    assert data["reasoning_share_of_completion"] == 0.9
    assert data["usd_total"] == pytest.approx(0.003)
    assert data["usd_per_1000_grievances"] == pytest.approx(0.03)


def test_an_unpriced_run_says_so_rather_than_reporting_zero_dollars():
    data = bench.UsageMeter().as_dict(items=10, price_in=0.0, price_out=0.0)
    assert "Not priced" in str(data["usd_total"])


# ── Invention metering (D-51) ────────────────────────────────────────────────


def test_the_invention_meter_still_sees_what_the_product_stopped_storing():
    """
    Since D-51 an off-catalogue category is repaired or dropped before it is returned, so the
    harness can no longer see invention in `predicted` — it would report a flattering 0 for any
    model, and the row that bought the six `Road Hazard - *` categories would quietly stop working.
    `InventionMeter` reads it from the resolution log instead.

    ⚠ **This test only covers the meter's own arithmetic** — it emits the log lines itself, so it
    cannot catch a rewording in `LLM_services.py`. The coupling to the *product's* wording is pinned
    where the product runs:
    `test_llm_services.py::test_the_benchmark_can_still_count_what_the_product_stopped_storing`.
    Both are needed; this one alone would go green on a fix that measures nothing.
    """
    import logging

    meter = bench.InventionMeter()
    meter.install()
    logger = logging.getLogger("llm_service")
    assert logger.getEffectiveLevel() <= logging.INFO, "install() must let repairs through"

    logger.warning(
        "classify_and_summarize_grievance: dropped %d category value(s) that exist "
        "nowhere in the live catalogue: %s", 1, ["Teleportation Damage"],
    )
    logger.info(
        "classify_and_summarize_grievance: repaired %d category value(s) onto the catalogue: %s",
        1, [("Wildlife Passage", "Wildlife, Environmental - Wildlife Passage")],
    )

    counts = meter.as_dict(105)
    assert counts["items_with_an_invented_category"] == 1
    assert counts["items_with_a_repaired_category"] == 1
    assert counts["rate_invented"] == round(1 / 105, 4)


def test_a_repair_is_not_counted_as_an_invention():
    """
    They are different findings. A repaired category is the model naming a real one badly — a
    formatting failure. An invented one is the model asking for a category that does not exist,
    which is the taxonomy signal. Collapsing them would have made the `Road Hazard` gap look like
    a spelling problem.
    """
    import logging

    meter = bench.InventionMeter()
    meter.install()
    logging.getLogger("llm_service").info(
        "classify_and_summarize_grievance: repaired %d category value(s) onto the catalogue: %s",
        2, [("Cultural Site Disturbances", "Cultural, Social - Cultural Site Disturbances")],
    )

    assert meter.as_dict(105)["items_with_an_invented_category"] == 0
