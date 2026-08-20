# SPDX-License-Identifier: Apache-2.0

"""
Probe an OpenAI-compatible endpoint and report what it can actually be *told*.

    python -m scripts.ops.llm_smoke                       # the registry's own models
    python -m scripts.ops.llm_smoke --candidates          # the DPG-23 shortlist
    python -m scripts.ops.llm_smoke --models a/b,c/d      # named models
    python -m scripts.ops.llm_smoke --audio note.ogg      # add a transcription probe
    python -m scripts.ops.llm_smoke --json report.json    # machine-readable, for the docs

Exit codes: 0 measured cleanly · 1 nothing answered · 3 the ACCOUNT blocked probes (402/401/429),
which is not the same as a model refusing a parameter and must never be recorded as one.

**Why this exists rather than a curl in a runbook.** DPG-13's degradation ladder assumes support for
`json_schema` is a property of the **(endpoint, model) pair**, and Sprint 1 measured that assumption
to be right: `gpt-3.5-turbo` 400s on `json_schema` and `gpt-4` 400s on `json_object` too. Open-weights
ids fall through `_PROFILES` to the conservative default by construction, which is safe and
pessimistic — it sends `json_object` to models that would have honoured a grammar. Turning that
pessimism into knowledge is one request per cell, and this is the thing that makes those requests.

⚠ **A silently-ignored `response_format` and an honoured one look identical from the outside**, which
is why every probe here asks for something a plain completion would get wrong — a schema with a
required field the prompt never mentions — instead of asking for "some JSON" and calling a parse a pass.

**The output is a `ModelProfile`, not prose.** ``backend/config/llm_config.py`` decides the strictest
usable rung per model from `_PROFILES`; a capability matrix that lives only in a markdown table is a
claim nothing enforces. This prints the tuple to paste, so the measurement lands in the code path that
runs. That is DPG-21's acceptance, and the failure it prevents is a provider quietly dropping
`json_schema` under load and returning malformed output nobody traced back to a docs page.

⚠ **Costs real money.** Every probe is a live inference call: roughly 6 requests per model, all tiny.
Read `--dry-run` first if you are unsure which endpoint is configured.

Spec: docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-21
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config.llm_config import (  # noqa: E402
    asr_endpoint,
    get_llm_settings,
    llm_endpoint,
    strict_json_schema,
)

CANDIDATES_FILE = Path(__file__).with_name("llm_candidates.json")

# The probe schema. Deliberately awkward: `district` is required and the prompt never says the word,
# so a model that ignores the schema omits it and a model that is *constrained* by the schema cannot.
# That is the difference between "returned JSON" and "was actually constrained", and asking for
# "some JSON" cannot tell them apart.
PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "district": {"type": "string"},
        "urgent": {"type": "boolean"},
    },
}
PROBE_PROMPT = (
    "A complainant in rural Nepal reports that road construction dust is entering their house and "
    "their children have become ill. Reply with JSON describing the complaint."
)


# Provider refusals that measure the ACCOUNT, not the model. Keeping these apart from a genuine
# capability refusal is the whole difference between a report and a misleading one: on 2026-08-20 a
# 402 "monthly credits depleted" rendered as ❌ against `temperature` and `max_tokens`, which reads
# exactly like "this model does not support them". That is the D-44 shape — a config error wearing
# the clothes of a quality finding — and the SEAH method doc §6.1 exists because of it.
_BLOCKED_MARKERS = (
    "401", "403", "402", "429", "insufficient", "credits", "quota", "billing",
    "payment required", "rate limit", "unauthorized", "authentication",
    "503", "502", "504", "overloaded", "timeout", "timed out", "connection",
)


@dataclass
class Probe:
    """One question asked of one model, and the exact answer the provider gave."""

    name: str
    ok: bool
    outcome: str = "pass"       # pass · refused (the model said no) · blocked (the account did)
    detail: str = ""
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    provider: str = ""


@dataclass
class ModelReport:
    model: str
    licence: str = "⚠ not checked"
    licence_source: str = ""
    probes: list[Probe] = field(default_factory=list)

    def find(self, name: str) -> Probe | None:
        return next((p for p in self.probes if p.name == name), None)

    def passed(self, name: str) -> bool:
        probe = self.find(name)
        return bool(probe and probe.ok)

    def blocked(self, name: str) -> bool:
        probe = self.find(name)
        return bool(probe and probe.outcome == "blocked")

    @property
    def any_blocked(self) -> bool:
        """
        True when the account, not the model, stopped at least one probe.

        ⚠ **A report with any blocked cell must not emit a ModelProfile.** The derivations below read
        a ❌ as "the model refuses this", and a profile built from a 402 would pin a *conservative*
        rung into the code path that runs, permanently, on evidence that measured nothing. Silent
        pessimism is cheaper than silent optimism and still wrong.
        """
        return any(p.outcome == "blocked" for p in self.probes)

    def cell(self, name: str) -> str:
        probe = self.find(name)
        if probe is None:
            return "·"
        return {"pass": "✅", "refused": "❌", "blocked": "⚠ blocked"}[probe.outcome]

    # ── The whole point: a ModelProfile, derived from measurement ────────────
    @property
    def structured_output(self) -> str:
        if self.passed("json_schema"):
            return "json_schema"
        if self.passed("json_object"):
            return "json_object"
        return "prompt"

    @property
    def token_cap_param(self) -> str:
        return "max_tokens" if self.passed("max_tokens") else "max_completion_tokens"

    @property
    def reasoning_overhead(self) -> int:
        """
        Headroom to add to a caller's token cap, rounded up to the next 500.

        ⚠ This is the field that bites silently. A cap that the reasoning phase consumes entirely
        returns ``finish_reason: length`` with **empty content** — not an error, not a truncation
        anyone notices, just nothing. D-40 cost 4,287 completion tokens against a cap of 1,200.
        Measured from one small probe, so treat it as a floor: a long ticket timeline reasons more
        than a two-line dust complaint.
        """
        peak = max((p.reasoning_tokens for p in self.probes), default=0)
        return 0 if peak == 0 else ((peak // 500) + 1) * 500

    @property
    def profile_tuple(self) -> str:
        prefix = self.model.split("/")[-1].split(":")[0]
        if self.any_blocked:
            unmeasured = sorted({p.name for p in self.probes if p.outcome == "blocked"})
            return f"# ⚠ {prefix}: NOT emitted — {', '.join(unmeasured)} blocked by the account, not the model"
        temperature = self.passed("temperature")
        return (
            f'("{prefix}", ModelProfile("{self.structured_output}", {temperature}, '
            f'"{self.token_cap_param}", {self.reasoning_overhead})),'
        )


def _client(base_url: str, api_key: str, timeout: float):
    try:
        from openai import OpenAI
    except ImportError:  # pragma: no cover - environment, not logic
        sys.exit(
            "openai is not installed. Run this in the stack, which is where the product runs:\n"
            "  docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \\\n"
            "    run --rm -v \"$PWD:/app\" -w /app ticketing_api python -m scripts.ops.llm_smoke"
        )
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0)


def _usage(response) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = getattr(details, "reasoning_tokens", 0) or 0 if details else 0
    return (
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
        reasoning,
    )


def _provider_of(response) -> str:
    """
    Which partner actually served this request.

    ⚠ Worth recording on every row: the Hugging Face router picks a partner **per request** unless
    the model id pins one, so "which company processed this text" is not knowable from configuration
    alone. That is fine for synthetic probes and is exactly what production must not do
    (privacy-assessment.md F-17).
    """
    for attribute in ("provider", "served_by"):
        value = getattr(response, attribute, None)
        if value:
            return str(value)
    raw = getattr(response, "model_extra", None) or {}
    for key in raw:
        if key.startswith("x_"):
            return key[2:]
    return ""


def _run(name: str, call) -> Probe:
    start = time.monotonic()
    try:
        response = call()
    except Exception as exc:  # noqa: BLE001 — the provider's exact refusal IS the measurement
        message = str(exc).replace("\n", " ")
        lowered = message.lower()
        blocked = any(marker in lowered for marker in _BLOCKED_MARKERS)
        return Probe(
            name=name,
            ok=False,
            outcome="blocked" if blocked else "refused",
            detail=message[:280],
            latency_s=round(time.monotonic() - start, 2),
        )
    prompt_tokens, completion_tokens, reasoning = _usage(response)
    return Probe(
        name=name,
        ok=True,
        outcome="pass",
        detail=_first_content(response)[:120],
        latency_s=round(time.monotonic() - start, 2),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        reasoning_tokens=reasoning,
        provider=_provider_of(response),
    )


def _first_content(response) -> str:
    try:
        return (response.choices[0].message.content or "").strip()
    except Exception:  # noqa: BLE001
        return ""


def probe_model(client, model: str, *, cap: int = 600) -> ModelReport:
    """Six questions, one request each. Each one is a thing a caller would otherwise assume."""
    report = ModelReport(model=model)
    messages = [{"role": "user", "content": PROBE_PROMPT}]

    report.probes.append(_run("chat", lambda: client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": "Reply with the word OK and nothing else."}],
    )))
    if not report.passed("chat"):
        return report  # nothing below is interpretable if the model will not answer at all

    report.probes.append(_run("json_object", lambda: client.chat.completions.create(
        model=model, messages=messages, response_format={"type": "json_object"},
    )))
    report.probes.append(_run("json_schema", lambda: client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "probe", "strict": True, "schema": strict_json_schema(PROBE_SCHEMA),
            },
        },
    )))
    report.probes.append(_run("temperature", lambda: client.chat.completions.create(
        model=model, messages=messages, temperature=0.2,
    )))
    report.probes.append(_run("max_tokens", lambda: client.chat.completions.create(
        model=model, messages=messages, max_tokens=cap,
    )))
    report.probes.append(_run("max_completion_tokens", lambda: client.chat.completions.create(
        model=model, messages=messages, max_completion_tokens=cap,
    )))

    # ⚠ A `json_schema` request that comes back WITHOUT the required key was accepted and ignored —
    # the silent-degradation case, and the one that produces malformed output under load. Downgrade
    # the verdict rather than reporting a pass, because a pass here is what a reader would act on.
    schema_probe = report.find("json_schema")
    if schema_probe and schema_probe.ok:
        try:
            parsed = json.loads(schema_probe.detail or "{}")
            missing = [k for k in PROBE_SCHEMA["properties"] if k not in parsed]
        except json.JSONDecodeError:
            missing = ["<unparseable>"]
        if missing:
            schema_probe.ok = False
            schema_probe.detail = (
                f"accepted but NOT honoured — reply omits {missing}. Silent degradation: "
                "the request succeeded and the grammar was not applied."
            )
    return report


def verify_licence(model: str) -> tuple[str, str]:
    """
    The licence, from the model card, at probe time — never from a table in a spec.

    Model tags move fast and a licence quoted from a plan is a claim about the past. Returns
    ``(licence, source-url)`` so the report can be audited rather than trusted.
    """
    if "/" not in model:
        return "n/a (not a Hugging Face id)", ""
    url = f"https://huggingface.co/api/models/{model}"
    try:
        with urllib.request.urlopen(url, timeout=20) as handle:  # noqa: S310 — fixed host
            data = json.load(handle)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return f"⚠ lookup failed: {exc}", url
    licence = (data.get("cardData") or {}).get("license")
    if not licence:
        for tag in data.get("tags", []):
            if tag.startswith("license:"):
                licence = tag.split(":", 1)[1]
                break
    return (licence or "⚠ none declared"), url


def _models_from_registry() -> list[str]:
    settings = get_llm_settings()
    names = [
        settings.model_classify, settings.model_extract, settings.model_translate,
        settings.model_detect, settings.model_ticket_findings, settings.model_ticket_findings_seah,
        settings.model_ticket_translate or settings.model_translate,
    ]
    return sorted({name for name in names if name})


def _models_from_candidates() -> list[str]:
    data = json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    return [entry["id"] for entry in data["shortlist"]]


def _render(reports: list[ModelReport], endpoint) -> None:
    columns = ("chat", "json_object", "json_schema", "temperature", "max_tokens", "max_completion_tokens")
    width = max((len(r.model) for r in reports), default=10) + 2

    print(f"\nEndpoint: {endpoint.host}   (structured-output ceiling: {endpoint.structured_output})")
    print("=" * (width + 78))
    print(f"{'model':<{width}}" + "".join(f"{c[:12]:<14}" for c in columns))
    print("-" * (width + 78))
    for report in reports:
        cells = "".join(f"{report.cell(c):<14}" for c in columns)
        print(f"{report.model:<{width}}{cells}")

    blocked = [r.model for r in reports if r.any_blocked]
    if blocked:
        print()
        print("⚠ " + "=" * 76)
        print("⚠  THE ACCOUNT BLOCKED PROBES — those cells measure billing, not capability.")
        print("⚠  Affected: " + ", ".join(blocked))
        print("⚠  Nothing here may be quoted as a model result, and no ModelProfile is emitted for")
        print("⚠  an affected model. Top the account up and re-run before recording anything.")
        print("⚠ " + "=" * 76)

    print("\nLicence — read from the model card at probe time, not from a spec table")
    print("-" * (width + 40))
    for report in reports:
        print(f"{report.model:<{width}}{report.licence}")

    print("\nFailures, in the provider's own words")
    print("-" * 78)
    any_failure = False
    for report in reports:
        for probe in report.probes:
            if not probe.ok:
                any_failure = True
                label = "⚠ BLOCKED" if probe.outcome == "blocked" else "refused  "
                print(f"  {label} {report.model} · {probe.name}: {probe.detail}")
    if not any_failure:
        print("  (none)")

    print("\nMeasured latency and token usage, per probe")
    print("-" * 78)
    for report in reports:
        served = {p.provider for p in report.probes if p.provider}
        chat = report.find("json_schema") or report.find("chat")
        if chat:
            print(
                f"  {report.model:<{width}} {chat.latency_s:>6.2f}s  "
                f"in={chat.prompt_tokens:<5} out={chat.completion_tokens:<5} "
                f"reasoning={chat.reasoning_tokens:<5} served_by={','.join(sorted(served)) or '?'}"
            )

    print("\n⭐ Paste into _PROFILES in backend/config/llm_config.py — first match wins, so order by")
    print("   specificity. A matrix that lives only in a document is a claim nothing enforces.")
    print("-" * 78)
    for report in reports:
        if report.passed("chat") or report.any_blocked:
            print(f"    {report.profile_tuple}")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--models", help="comma-separated model ids to probe")
    source.add_argument("--candidates", action="store_true", help="probe the DPG-23 shortlist")
    parser.add_argument("--audio", type=Path, help="audio file for a transcription probe")
    parser.add_argument("--json", type=Path, help="write the full report here")
    parser.add_argument("--no-licence", action="store_true", help="skip model-card licence lookups")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and spend nothing")
    args = parser.parse_args()

    endpoint = llm_endpoint()
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    elif args.candidates:
        models = _models_from_candidates()
    else:
        models = _models_from_registry()

    if not endpoint.api_key:
        print("⚠ No API key resolved (LLM_API_KEY / OPENAI_API_KEY). Nothing to probe.", file=sys.stderr)
        return 2

    print(f"Endpoint : {endpoint.host}")
    print(f"Models   : {', '.join(models)}")
    print(f"Requests : {len(models)} × 6 chat probes" + (" + 1 transcription" if args.audio else ""))
    if args.dry_run:
        print("\n--dry-run: nothing sent.")
        return 0

    client = _client(endpoint.base_url, endpoint.api_key, endpoint.timeout)
    reports: list[ModelReport] = []
    for model in models:
        print(f"  probing {model} …", flush=True)
        report = probe_model(client, model)
        if not args.no_licence:
            report.licence, report.licence_source = verify_licence(model)
        reports.append(report)

    _render(reports, endpoint)

    audio_result = None
    if args.audio:
        audio_result = _probe_audio(args.audio)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "endpoint": endpoint.host,
                    "structured_output_ceiling": endpoint.structured_output,
                    "models": [asdict(r) | {"profile_tuple": r.profile_tuple} for r in reports],
                    "audio": audio_result,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Report written to {args.json}")

    # Exit codes: 0 measured cleanly · 1 nothing answered at all · 3 the account blocked probes.
    # A model that refuses `json_schema` is a measurement and stays 0 — this script reports, it does
    # not gate. A 402 is a different thing entirely and must not exit green, or a scheduled run
    # leaves a green log beside an empty matrix and nobody looks again.
    # Blocked takes precedence over "nothing answered": both are true when the account is empty, and
    # only one of them tells you what to do about it. 1 sends you to look at the endpoint; 3 sends
    # you to look at the bill.
    if any(r.any_blocked for r in reports):
        return 3
    return 0 if any(r.passed("chat") for r in reports) else 1


def _probe_audio(path: Path) -> dict:
    """Transcription against the ASR endpoint, which may be a different host entirely."""
    endpoint = asr_endpoint()
    model = get_llm_settings().model_asr
    print(f"\nTranscription probe: {model} on {endpoint.host}")
    if not path.is_file():
        print(f"  ⚠ {path} does not exist — skipped")
        return {"ok": False, "detail": "audio file not found", "model": model}
    client = _client(endpoint.base_url, endpoint.api_key, endpoint.timeout)
    start = time.monotonic()
    try:
        with path.open("rb") as handle:
            # ⚠ `language`, not `language_code` — DPG-14.3 found every transcription raising
            # TypeError on the wrong keyword, on a path nothing exercised in production.
            result = client.audio.transcriptions.create(model=model, file=handle, language="ne")
    except Exception as exc:  # noqa: BLE001
        detail = str(exc).replace("\n", " ")[:280]
        print(f"  ❌ {detail}")
        return {"ok": False, "detail": detail, "model": model}
    elapsed = round(time.monotonic() - start, 2)
    text = getattr(result, "text", "") or ""
    print(f"  ✅ {elapsed}s · {len(text)} chars · {text[:120]}")
    return {"ok": True, "model": model, "latency_s": elapsed, "text": text}


if __name__ == "__main__":
    raise SystemExit(main())
