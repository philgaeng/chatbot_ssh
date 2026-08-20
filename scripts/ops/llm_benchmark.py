# SPDX-License-Identifier: Apache-2.0

"""
Score a model against this project's own benchmark set — DPG-23.

    python -m scripts.ops.llm_benchmark --estimate                 # price it, spend nothing
    python -m scripts.ops.llm_benchmark --models gpt-5-nano        # the closed baseline
    python -m scripts.ops.llm_benchmark --candidates --sample 20   # the cheap first pass
    python -m scripts.ops.llm_benchmark --seah-set /path/out/of/repo.jsonl

**It runs the product's own call path, not a reimplementation of it.** `classify_and_summarize_grievance`
and `detect_sensitive_content_llm` are the functions the chatbot calls, with the prompts the chatbot
sends, resolved through the registry the chatbot reads. That is what makes this a **pre-flight check
on a production change** (Q-04: production will run the open configuration) rather than a parallel
universe that agrees with production only by luck.

⚠ **Three things this harness does that a naive one would get wrong, each from something already
recorded in this sprint:**

1. **Prove the credential before reporting a single miss.** A 401 or a 402 renders as *"the model
   failed to detect harassment"* — a config error wearing the clothes of a quality finding (D-44,
   D-50, and `docs/models/01_seah_detection_benchmark.md` §6.1). A known-good item runs first and
   the harness aborts if it does not come back clean.
2. **Normalise the category strings before comparing them.** The prompt shows the model the *raw*
   taxonomy values (`LLM_services.py:263`) while the canonical key is title-cased with hyphens
   replaced. Grading one against the other deflates every score by the width of that mismatch and
   looks exactly like a model problem (`tests/data/benchmark/README.md` §4.1).
3. **Measure latency without the interactive deadline truncating it.** Calls run with
   `interactive=False`, so a slow model produces a *number* instead of a timeout, and the report
   says what fraction would have missed 30 s / 45 s / 60 s. Measuring under a 30 s cap would make
   every candidate look like it just fits.

⚠ **The committed set cannot measure SEAH recall.** It carries the false-alarm half only — the
harassment narratives are held by the project owner and never enter this repository (§0.2 of the
sprint spec). Point `--seah-set` at that file to get recall; without it the report says
`⚠ Not measured` rather than implying a pass.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-23
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BENCHMARK_DIR = REPO_ROOT / "tests" / "data" / "benchmark"
GENERAL_SET = BENCHMARK_DIR / "general_classification.jsonl"
CANDIDATES_FILE = Path(__file__).with_name("llm_candidates.json")

# The interactive budget, and the two raises the owner has said are available (2026-08-20: "a knob,
# not a wall"). Reported against all three so a recommendation carries its cost.
LATENCY_BUDGETS_S = (30.0, 45.0, 60.0)


# ── Category normalisation (README §4.1) ─────────────────────────────────────


def canonical_category(raw: str) -> str:
    """
    Fold a model's reply into the canonical key form the benchmark labels use.

    Mirrors ``load_classification_data``'s key construction — hyphens to spaces, title case, per
    half — but splits on the ``" - "`` separator first, because several category names contain a
    hyphen of their own (``Gender-Based Access Issues``) and a blanket replace would destroy the
    separator along with them.
    """
    text = (raw or "").strip().strip('"\'')
    if " - " not in text:
        return text.replace("-", " ").title()
    classification, _, name = text.partition(" - ")
    return f"{classification.replace('-', ' ').title()} - {name.replace('-', ' ').title()}"


# ── Token metering ───────────────────────────────────────────────────────────


class UsageMeter:
    """
    Count what the run actually spends, by wrapping the client the product builds.

    ⚠ **This exists because the product records no token usage anywhere.** `call_llm` returns a
    parsed object and drops `response.usage` on the floor, so the running system cannot answer
    *"what did last month cost"* — which matters more here than it usually would, because
    [Q-19](../../docs/sprints/2026-08-llm/DECISIONS.md)'s envelope is **shared between this
    benchmark and the pilot's own classification traffic across two districts**. You cannot subtract
    pilot traffic from a budget you do not measure. Logged as a follow-up; metering here rather than
    changing a stable service in a benchmark commit.

    Wrapping the client instead of estimating from character counts matters for a second reason:
    reasoning tokens are invisible in the reply and dominate the bill — 92% of one measured call
    (D-30). An estimate from output length understates a reasoning model by an order of magnitude.
    """

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.reasoning_tokens = 0
        self.calls = 0
        self._original = None

    def install(self) -> None:
        from backend.services import llm_client

        client = llm_client.get_llm_client()
        completions = client.chat.completions
        if self._original is not None:
            return
        self._original = completions.create

        def metered(*args, **kwargs):
            response = self._original(*args, **kwargs)
            usage = getattr(response, "usage", None)
            if usage is not None:
                self.calls += 1
                self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
                self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
                details = getattr(usage, "completion_tokens_details", None)
                if details is not None:
                    self.reasoning_tokens += getattr(details, "reasoning_tokens", 0) or 0
            return response

        completions.create = metered

    def as_dict(self, items: int, price_in: float, price_out: float) -> dict:
        data = {
            "calls": self.calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "reasoning_share_of_completion": (
                round(self.reasoning_tokens / self.completion_tokens, 4)
                if self.completion_tokens else None
            ),
        }
        if price_in or price_out:
            cost = (self.prompt_tokens / 1e6) * price_in + (self.completion_tokens / 1e6) * price_out
            data["usd_total"] = round(cost, 4)
            data["usd_per_1000_grievances"] = round(cost / items * 1000, 2) if items else None
            data["price_basis"] = f"${price_in}/M prompt, ${price_out}/M completion — supply the date you read these"
        else:
            data["usd_total"] = "⚠ Not priced — pass --price-in / --price-out"
        return data


# ── Results ──────────────────────────────────────────────────────────────────


@dataclass
class ItemResult:
    item_id: str
    ok: bool
    blocked: bool = False
    latency_s: float = 0.0
    predicted: list[str] = field(default_factory=list)
    gold: list[str] = field(default_factory=list)
    acceptable: list[str] = field(default_factory=list)
    summary_chars: int = 0
    detected_sensitive: bool | None = None
    expected_sensitive: bool | None = None
    error: str = ""


@dataclass
class Scores:
    model: str
    task: str
    items: list[ItemResult] = field(default_factory=list)

    @property
    def usable(self) -> list[ItemResult]:
        return [r for r in self.items if r.ok]

    @property
    def blocked(self) -> list[ItemResult]:
        return [r for r in self.items if r.blocked]

    # ── Classification, scored SET-LEVEL (DPG-23 acceptance) ─────────────────
    def set_level(self) -> dict:
        """
        Micro-averaged precision / recall / F1 over category **sets**, plus exact-set accuracy.

        ⚠ Single-label accuracy would misrepresent this system: it returns `grievance_categories`
        **and** `grievance_categories_alternative`, and eight items in the set genuinely carry two
        gold labels. A model naming both would score 0 on a single-label metric.

        `categories_acceptable` is neither rewarded nor penalised — a defensible neighbour is not a
        false positive, and counting it as one would punish exactly the behaviour the alternates
        list exists to produce.
        """
        tp = fp = fn = 0
        exact = 0
        for result in self.usable:
            predicted, gold = set(result.predicted), set(result.gold)
            acceptable = set(result.acceptable)
            tp += len(predicted & gold)
            fp += len(predicted - gold - acceptable)
            fn += len(gold - predicted)
            if predicted & gold == gold and not (predicted - gold - acceptable):
                exact += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        n = len(self.usable)
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "exact_set_accuracy": round(exact / n, 4) if n else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "n": n,
        }

    # ── Sensitive detection, scored RECALL-FIRST ─────────────────────────────
    def detection(self) -> dict:
        """
        A confusion matrix, never a single number.

        A **miss** is a safeguarding failure. A **false alarm** routes an ordinary complaint into a
        channel most officers cannot see, so the dust or compensation problem effectively disappears.
        Those costs are not symmetric and one number hides that
        (`docs/models/01_seah_detection_benchmark.md` §1).
        """
        scored = [r for r in self.usable if r.expected_sensitive is not None]
        tp = sum(1 for r in scored if r.expected_sensitive and r.detected_sensitive)
        fn = sum(1 for r in scored if r.expected_sensitive and not r.detected_sensitive)
        fp = sum(1 for r in scored if not r.expected_sensitive and r.detected_sensitive)
        tn = sum(1 for r in scored if not r.expected_sensitive and not r.detected_sensitive)
        positives = tp + fn
        negatives = fp + tn
        return {
            "recall": round(tp / positives, 4) if positives else None,
            "false_alarm_rate": round(fp / negatives, 4) if negatives else None,
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "positive_scenarios": positives,
            "negative_scenarios": negatives,
            # ⚠ Stated in the data, not left for the reader to infer from a null.
            "recall_note": (
                None if positives else
                "⚠ Not measured — no positive scenarios in this set. The committed benchmark carries "
                "the false-alarm half only; the harassment narratives are held by the project owner "
                "and never enter this repository. Pass --seah-set to measure recall."
            ),
        }

    # ── Latency, against a budget that is a knob ─────────────────────────────
    def latency(self) -> dict:
        samples = sorted(r.latency_s for r in self.usable)
        if not samples:
            return {"note": "⚠ Not measured — no successful calls"}

        def percentile(p: float) -> float:
            index = min(int(round(p * (len(samples) - 1))), len(samples) - 1)
            return round(samples[index], 2)

        over = {
            f"over_{int(budget)}s": round(
                sum(1 for s in samples if s > budget) / len(samples), 4
            )
            for budget in LATENCY_BUDGETS_S
        }
        return {
            "n": len(samples),
            "p50": percentile(0.50), "p95": percentile(0.95), "p99": percentile(0.99),
            "max": round(samples[-1], 2), "mean": round(statistics.mean(samples), 2),
            **over,
        }


# ── The run ──────────────────────────────────────────────────────────────────


def _load_items(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _is_blocked(message: str) -> bool:
    from scripts.ops.llm_smoke import _BLOCKED_MARKERS

    lowered = message.lower()
    return any(marker in lowered for marker in _BLOCKED_MARKERS)


def _classify_one(item: dict) -> ItemResult:
    from backend.services.LLM_services import classify_and_summarize_grievance

    start = time.monotonic()
    try:
        # ⚠ interactive=False on purpose: the 30 s interactive deadline would truncate the very
        # measurement this run exists to produce. Latency is reported against 30/45/60 s afterwards.
        raw = classify_and_summarize_grievance(
            item["text"],
            language_code="ne" if item["script"] in ("devanagari", "roman_nepali") else "en",
            complainant_district=item["district"],
            interactive=False,
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        return ItemResult(item["id"], False, _is_blocked(message), round(time.monotonic() - start, 2),
                          error=message[:280])
    elapsed = round(time.monotonic() - start, 2)

    if raw.get("skipped"):
        return ItemResult(item["id"], False, False, elapsed, error=f"skipped: {raw['skipped']}")
    if raw.get("status") == "error" or raw.get("error"):
        message = str(raw.get("error") or "error")
        return ItemResult(item["id"], False, _is_blocked(message), elapsed, error=message[:280])

    predicted = [canonical_category(c) for c in (raw.get("grievance_categories") or [])]
    return ItemResult(
        item_id=item["id"],
        ok=True,
        latency_s=elapsed,
        predicted=predicted,
        gold=item["categories"],
        acceptable=item["categories_acceptable"],
        summary_chars=len(raw.get("grievance_summary") or ""),
    )


def _detect_one(item: dict) -> ItemResult:
    from backend.services.LLM_services import detect_sensitive_content_llm

    start = time.monotonic()
    try:
        raw = detect_sensitive_content_llm(
            item["text"], language_code="ne" if item["script"] in ("devanagari", "roman_nepali") else "en",
        )
    except Exception as exc:  # noqa: BLE001
        message = str(exc)
        return ItemResult(item["id"], False, _is_blocked(message), round(time.monotonic() - start, 2),
                          error=message[:280])
    return ItemResult(
        item_id=item["id"],
        ok=True,
        latency_s=round(time.monotonic() - start, 2),
        detected_sensitive=bool(raw.get("detected")),
        expected_sensitive=bool(item.get("sensitive", False)),
    )


def _prove_the_credential(items: list[dict], task: str) -> None:
    """
    ⚠ **Run one item and insist it comes back clean before scoring anything.**

    ``docs/models/01_seah_detection_benchmark.md`` §6.1 makes this a requirement, from an incident:
    a 401 presented as *"the model cannot detect harassment"*, because the SEAH path fails open by
    design. D-50 is the same thing again with a 402. A harness that skips this eventually publishes
    a broken key as a model result.
    """
    probe = _classify_one(items[0]) if task == "classify" else _detect_one(items[0])
    if probe.ok:
        return
    raise SystemExit(
        f"\n⚠ ABORTING BEFORE SCORING — the first item did not come back clean.\n"
        f"   item : {probe.item_id}\n"
        f"   error: {probe.error}\n"
        f"   {'This is an ACCOUNT or TRANSPORT failure, not a model result.' if probe.blocked else ''}\n"
        f"   Nothing measured. Fix the credential or the endpoint and re-run; a run that scores "
        f"through this publishes a config error as a quality finding.\n"
    )


def run_task(model: str, task: str, items: list[dict], concurrency: int) -> Scores:
    from backend.config.llm_config import get_llm_settings

    env_var = {"classify": "MODEL_CLASSIFY", "detect": "MODEL_DETECT"}[task]
    os.environ[env_var] = model
    get_llm_settings.cache_clear()

    print(f"\n▶ {model} · {task} · {len(items)} items · concurrency {concurrency}")
    _prove_the_credential(items, task)

    worker = _classify_one if task == "classify" else _detect_one
    scores = Scores(model=model, task=task)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for index, result in enumerate(pool.map(worker, items), 1):
            scores.items.append(result)
            if index % 10 == 0 or index == len(items):
                print(f"    {index}/{len(items)}", flush=True)

    blocked = scores.blocked
    if blocked:
        print(f"  ⚠ {len(blocked)} item(s) BLOCKED by the account/transport — not model results")
    return scores


# ── Pricing, before anything is spent ────────────────────────────────────────


def estimate(items: list[dict], models: list[str], tasks: list[str]) -> dict:
    """
    ⚠ **"Priced before built" is a DPG-23 acceptance criterion, so this is a mode, not a footnote.**

    Token counts are the measurement and they do not drift. Dollar figures do, so they are computed
    from a rate the caller supplies with a date rather than baked in here — a price hard-coded in a
    script is wrong within a quarter and nobody notices.

    ⚠ **The prompt dominates, and by a lot.** Classification injects the whole 24-category catalogue
    **twice, in two shapes** — measured at 20,725 characters on the live path (D-30). So cost scales
    with the catalogue, not with the grievance, and a 105-item run is ~105 × that prompt whatever the
    complaints say.
    """
    # Rebuild the catalogue exactly as the prompt does, so the estimate prices the real request
    # rather than a guess at it.
    from backend.config.constants import CLASSIFICATION_DATA as catalogue

    category_list = [
        f"{v.get('classification')} - {v.get('generic_grievance_name')}" for v in catalogue.values()
    ]
    result_dict = {k: {kk: vv for kk, vv in v.items() if "_ne" not in kk} for k, v in catalogue.items()}
    catalogue_chars = len(json.dumps(category_list)) * 2 + len(json.dumps(result_dict))

    item_chars = sum(len(i["text"]) for i in items)
    # ~4 characters per token for Latin script; Devanagari tokenises far worse — often 1–2 characters
    # per token — so this is a FLOOR for a set that is 41% Devanagari. Stated, not hidden.
    prompt_tokens = (catalogue_chars * len(items) + item_chars) // 4
    completion_tokens = len(items) * 900   # summary + two category lists + reasoning, generously

    per_model_task = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
    runs = len(models) * len(tasks)
    return {
        "items": len(items),
        "models": models,
        "tasks": tasks,
        "runs": runs,
        "per_run": per_model_task,
        "total_prompt_tokens": prompt_tokens * runs,
        "total_completion_tokens": completion_tokens * runs,
        "caveats": [
            "Prompt tokens are a FLOOR: ~4 chars/token assumes Latin script, and 41% of this set is "
            "Devanagari, which commonly tokenises at 1-2 chars/token. Expect 1.5-2x on the Nepali half.",
            "Completion allowance is generous BECAUSE reasoning models spend most of it invisibly — "
            "92% of one measured gpt-5-nano run was reasoning tokens (D-30).",
            "The catalogue is injected TWICE per call, in two shapes (LLM_services.py:263-267), so "
            "cost scales with the taxonomy rather than with the grievance.",
        ],
    }


def _print_estimate(data: dict, price_in: float, price_out: float) -> None:
    print("\nCost estimate — nothing has been sent")
    print("=" * 78)
    print(f"  items per run     : {data['items']}")
    print(f"  runs              : {data['runs']}  ({len(data['models'])} model(s) × {len(data['tasks'])} task(s))")
    print(f"  prompt tokens     : {data['total_prompt_tokens']:,}")
    print(f"  completion tokens : {data['total_completion_tokens']:,}")
    if price_in or price_out:
        cost = (data["total_prompt_tokens"] / 1e6) * price_in + (data["total_completion_tokens"] / 1e6) * price_out
        print(f"  ⇒ at ${price_in}/M in, ${price_out}/M out : ${cost:,.2f}")
        print(f"  ⇒ per 1,000 grievances (classify only)   : ${cost / max(data['runs'], 1) / max(data['items'], 1) * 1000:,.2f}")
    else:
        print("  ⇒ pass --price-in and --price-out (USD per million tokens, with the date you read them)")
    print("\n  Caveats that change the number, not footnotes:")
    for caveat in data["caveats"]:
        print(f"    ⚠ {caveat}")
    print()


# ── Reporting ────────────────────────────────────────────────────────────────


def _report(all_scores: list[Scores]) -> dict:
    out: dict = {}
    for scores in all_scores:
        block = out.setdefault(scores.model, {})
        entry = {
            "n_items": len(scores.items),
            "n_ok": len(scores.usable),
            "n_blocked": len(scores.blocked),
            "latency": scores.latency(),
        }
        if scores.task == "classify":
            entry["set_level"] = scores.set_level()
            summaries = [r.summary_chars for r in scores.usable]
            entry["summary_chars_mean"] = round(statistics.mean(summaries), 1) if summaries else 0
        else:
            entry["detection"] = scores.detection()
        # ⚠ Per-item detail, always. `docs/models/01_seah_detection_benchmark.md` §6.3: record the
        # raw reply, not just the verdict — a miss caused by a truncation or a schema violation is a
        # different problem from a miss caused by judgement, and an aggregate cannot tell them apart.
        entry["items"] = [
            {
                "id": r.item_id, "ok": r.ok, "blocked": r.blocked, "latency_s": r.latency_s,
                "predicted": r.predicted, "gold": r.gold, "acceptable": r.acceptable,
                "detected_sensitive": r.detected_sensitive,
                "expected_sensitive": r.expected_sensitive,
                "error": r.error,
            }
            for r in scores.items
        ]
        if scores.blocked:
            entry["warning"] = (
                f"⚠ {len(scores.blocked)} item(s) failed on the ACCOUNT or transport, not the model. "
                "These are excluded from every score above and the remaining sample is smaller than "
                "the set — say so wherever these numbers are published."
            )
        block[scores.task] = entry
    return out


def _print_usage(usage: dict) -> None:
    print("Measured token usage — what this run actually spent")
    print("=" * 78)
    print(f"  calls              : {usage['calls']}")
    print(f"  prompt tokens      : {usage['prompt_tokens']:,}")
    print(f"  completion tokens  : {usage['completion_tokens']:,}")
    share = usage.get("reasoning_share_of_completion")
    print(f"  of which reasoning : {usage['reasoning_tokens']:,}"
          + (f"  ({share:.1%} of completion — invisible in the reply, visible on the bill)" if share else ""))
    print(f"  cost               : {usage['usd_total']}")
    if usage.get("usd_per_1000_grievances") is not None:
        print(f"  per 1,000 grievances: ${usage['usd_per_1000_grievances']}  "
              "← one half of the costed proposal Q-19 commits to")
    print()


def _print_report(report: dict) -> None:
    for model, tasks in report.items():
        if model == "_usage":
            continue
        print(f"\n{model}")
        print("=" * 78)
        for task, entry in tasks.items():
            print(f"  {task}: {entry['n_ok']}/{entry['n_items']} scored"
                  + (f"  ⚠ {entry['n_blocked']} blocked" if entry["n_blocked"] else ""))
            if "set_level" in entry:
                s = entry["set_level"]
                print(f"    set-level  P={s['precision']:.3f}  R={s['recall']:.3f}  F1={s['f1']:.3f}"
                      f"  exact-set={s['exact_set_accuracy']:.3f}   (tp={s['tp']} fp={s['fp']} fn={s['fn']})")
                print(f"    summary    mean {entry['summary_chars_mean']} chars")
            if "detection" in entry:
                d = entry["detection"]
                recall = "⚠ Not measured" if d["recall"] is None else f"{d['recall']:.3f}"
                alarm = "n/a" if d["false_alarm_rate"] is None else f"{d['false_alarm_rate']:.3f}"
                print(f"    recall     {recall}   (positive scenarios: {d['positive_scenarios']})")
                print(f"    false alarm {alarm}   (negative scenarios: {d['negative_scenarios']})")
                if d.get("recall_note"):
                    print(f"    {d['recall_note']}")
            latency = entry["latency"]
            if "p50" in latency:
                budgets = "  ".join(f">{int(b)}s: {latency[f'over_{int(b)}s']:.1%}" for b in LATENCY_BUDGETS_S)
                print(f"    latency    p50={latency['p50']}s  p95={latency['p95']}s  p99={latency['p99']}s"
                      f"  max={latency['max']}s")
                print(f"               {budgets}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--models", help="comma-separated model ids")
    source.add_argument("--candidates", action="store_true", help="the DPG-23 shortlist")
    parser.add_argument("--tasks", default="classify,detect", help="classify,detect")
    parser.add_argument("--sample", type=int, help="first N items — the cheap first pass")
    parser.add_argument("--seah-set", type=Path, help="held-out SEAH set (NEVER in this repository)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--estimate", action="store_true", help="price it and send nothing")
    parser.add_argument("--price-in", type=float, default=0.0, help="USD per million prompt tokens")
    parser.add_argument("--price-out", type=float, default=0.0, help="USD per million completion tokens")
    parser.add_argument("--json", type=Path, help="write the full report here")
    args = parser.parse_args()

    items = _load_items(GENERAL_SET)
    if args.seah_set:
        if args.seah_set.resolve().is_relative_to(REPO_ROOT):
            return _refuse_in_repo_seah_set(args.seah_set)
        items = items + _load_items(args.seah_set)
        print(f"⚠ SEAH set loaded from outside the repository: {args.seah_set} "
              f"({len(items) - len(_load_items(GENERAL_SET))} items). Numbers from it are NOT "
              f"reproducible from this repository — say so wherever they are published.")
    if args.sample:
        items = items[: args.sample]

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    elif args.candidates:
        models = [e["id"] for e in json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))["shortlist"]]
    else:
        from backend.config.llm_config import get_llm_settings

        models = [get_llm_settings().model_classify]
    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]

    if args.estimate:
        _print_estimate(estimate(items, models, tasks), args.price_in, args.price_out)
        return 0

    meter = UsageMeter()
    meter.install()
    all_scores = [run_task(model, task, items, args.concurrency) for model in models for task in tasks]
    report = _report(all_scores)
    usage = meter.as_dict(len(items) * max(len(models), 1), args.price_in, args.price_out)
    report["_usage"] = usage
    _print_report(report)
    _print_usage(usage)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Report written to {args.json}")
    return 3 if any(s.blocked for s in all_scores) else 0


def _refuse_in_repo_seah_set(path: Path) -> int:
    """
    ⚠ The one hard refusal in this file.

    The owner decided on 2026-08-19 that SEAH narratives never enter this repository, and the reason
    is not squeamishness: *"three hundred realistic Nepali harassment complaints sitting in it will
    be read as leaked case data by somebody, regardless of how the file is labelled"*. A path inside
    the repo means somebody is about to commit one.
    """
    print(
        f"\n⚠ REFUSING: --seah-set points inside the repository ({path}).\n"
        "   SEAH narratives are held by the project owner and never committed —\n"
        "   docs/models/01_seah_detection_benchmark.md §3.3. Move the file outside the repo\n"
        "   and pass an absolute path to it.\n",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
