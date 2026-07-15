"""
T3-07 — the ``ticketing.*`` ↔ ``public.*`` boundary contract.

**Every test here is green on today's code, and that is the point.** They pin invariants;
they do *not* fix a bug. Do not "repair" a passing test by loosening it — if one goes red,
the boundary moved, and the question is whether that was deliberate. If it was, amend
``CLAUDE.md`` §Data rules **and** this file in the same commit.

The policy: ``CLAUDE.md`` §Data rules as amended 2026-07-15. Evidence and the decision:
``docs/sprints/archive/2026-08_tier3_structural/00-reassessment.md`` §6.

  * **Rule 1** — ticketing may read *and write* ``public.*``, but only the ``CONTRACT`` set
    below. Until 2026-07-15 the rule read "no SQL joins into ``public.*``", which had been
    false for months and was enforced by nothing. **The allowlist IS the contract** — it is
    what makes rule 1 enforceable rather than aspirational.
  * **Rule 2** — no cross-schema FK. → ``test_no_cross_schema_foreign_keys*``
  * **Rule 3** — no complainant PII columns in ``ticketing.*``, and ``public.complainants``
    is not a PII source for ticketing. → ``test_*_pii_*``

Rules 2 and 3 were kept because they hold and cost nothing. Rule 1's predecessor was dropped
because honoring it would have *degraded* security (§6): the direct read carries a Keycloak
JWT and a jurisdiction gate that ``GET /api/grievance/{id}`` still cannot offer even after
T3-06 (D-38).

**How drift is caught, and by what.** These tests are DB-free. They read
``migrations/public/expected_public_schema.sql`` — the CL-01 canonical baseline that CI
already asserts equals the freshly-migrated public schema
(``scripts/ci/check_public_schema_baseline.sh``). That gives a complete chain::

    real public schema  ──(CL-01 gate, in CI)──  expected_public_schema.sql
                                                          │
                                                  (this file)
                                                          │
                                              ticketing's CONTRACT + its SQL

So a column renamed in ``public.*`` fails the CL-01 gate → the baseline is regenerated →
*these* tests go red naming the ticketing code that will break. Same approach as
``tests/backend/test_grievance_response_contract.py`` (T3-06 / D-28).

**This file absorbs the standing ``grievance_sync.py`` hardcoded-column-list TODO row**
(TODO.md 🔵 TECH DEBT — "will break if public schema column names change"). That column list
is now declared and gated here, so the break surfaces in CI rather than at 02:00 in a Celery
beat job.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SQL = REPO_ROOT / "migrations" / "public" / "expected_public_schema.sql"
TICKETING = REPO_ROOT / "ticketing"
MIGRATIONS = TICKETING / "migrations" / "versions"

# ── Rule 1: the closed read/write contract ──────────────────────────────────
#
# Measured 2026-07-15 (§6, re-verified against this tree): 11 statements, 5 tables,
# 3 writes. Mirrors the table in CLAUDE.md §Data rules rule 1 — keep them in step.
#
# ADDING A TABLE HERE IS A DELIBERATE ARCHITECTURAL DECISION, NOT A DEFAULT.
# It widens the surface that must survive a chatbot-side schema change, and it spends
# the extraction optionality rule 2 exists to protect. Amend CLAUDE.md with it.
CONTRACT: dict[str, set[str]] = {
    # services/grievance_content.py (9 cols) · tasks/grievance_sync.py (10 cols)
    "grievances": {
        "grievance_id",
        "complainant_id",
        "grievance_summary",
        "grievance_categories",
        "grievance_description",
        "grievance_location",
        "grievance_classification_status",
        "grievance_high_priority",
        "grievance_sensitive_issue",
        "grievance_creation_date",
        "grievance_modification_date",
        "source",
    },
    # api/ticket_access.py · api/routers/tickets/files.py · engine/ticket_actions.py
    # · services/archiving.py (the UPDATE writes storage_tier/storage_key/archived_at)
    "file_attachments": {
        "file_id",
        "file_name",
        "file_path",
        "file_type",
        "file_size",
        "upload_timestamp",
        "grievance_id",
        "storage_tier",
        "storage_key",
        "archived_at",
    },
    # services/grievance_categories_catalog.py — SELECT, plus a DELETE+INSERT resync.
    # seed/kl_road_standard.py does a COUNT(*) (names no column).
    "grievance_classification_taxonomy": {
        "category_key",
        "generic_grievance_name",
        "generic_grievance_name_ne",
        "short_description",
        "short_description_ne",
        "classification",
        "classification_ne",
        "description",
        "description_ne",
        "follow_up_question_description",
        "follow_up_question_description_ne",
        "follow_up_question_quantification",
        "follow_up_question_quantification_ne",
        "high_priority",
    },
    # tasks/grievance_sync.py — join-only, and deliberately NON-PII (rule 3).
    "complainants": {"complainant_id", "location_code"},
    # tasks/grievance_sync.py — join-only.
    "grievance_parties": {"grievance_id", "complainant_id", "is_primary_reporter"},
}

# Census pin. 11 statements measured 2026-07-15. If this moves, the boundary moved:
# update CONTRACT + CLAUDE.md rule 1's table together, in the same commit.
EXPECTED_STATEMENT_COUNT = 11

# ── Rule 3: complainant PII ─────────────────────────────────────────────────
# base_manager.py:63-68 ENCRYPTED_FIELDS — the four columns public.complainants
# encrypts. Ticketing must neither store them nor select them.
PII_COLUMNS = frozenset(
    {
        "complainant_full_name",
        "complainant_phone",
        "complainant_email",
        "complainant_address",
    }
)
# The complainant_* columns ticketing may declare. Anything else under this namespace
# needs justification — that is the point of the fence.
ALLOWED_COMPLAINANT_COLUMNS = frozenset(
    {
        # Opaque string ref, no FK (CLAUDE.md §SQLAlchemy).
        "complainant_id",
        # NOT complainant data despite the prefix: parse it (complainant_reply)_owner_id.
        # It is the user_id of the *officer* holding the "reply to complainant" duty
        # (models/ticket.py:100-103). Declared so the fence below stays a real fence.
        "complainant_reply_owner_id",
    }
)

_CREATE_TABLE_RE = re.compile(r"CREATE TABLE public\.(\w+) \((.*?)\n\);", re.DOTALL)
_NON_COLUMN_PREFIX = ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "EXCLUDE")
# Anchored on clause position, not a bare "public.x" mention. Prose says "aligned with
# public.grievances" (grievance_sync.py:2) and "the chatbot's public.complainants table"
# (grievance_api.py:153); SQL says FROM/JOIN/INTO/UPDATE public.x. Matching the bare
# mention pulls docstrings in as statements — measured: 13 found, 11 real.
_PUBLIC_TABLE_RE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+public\.(\w+)", re.IGNORECASE)
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


# ── baseline (CL-01) ────────────────────────────────────────────────────────
def _parse_baseline_columns() -> dict[str, set[str]]:
    """``{table: {column, ...}}`` from the committed pg_dump baseline."""
    sql = BASELINE_SQL.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for table, body in _CREATE_TABLE_RE.findall(sql):
        columns: set[str] = set()
        for raw in body.splitlines():
            line = raw.strip().rstrip(",")
            if not line or line.upper().startswith(_NON_COLUMN_PREFIX):
                continue
            columns.add(line.split()[0])
        tables[table] = columns
    return tables


@pytest.fixture(scope="module")
def baseline() -> dict[str, set[str]]:
    tables = _parse_baseline_columns()
    # Guard the guard: a silently-empty parse makes every assertion below vacuous.
    for table in CONTRACT:
        assert tables.get(table), f"parsed no columns for public.{table}"
    return tables


# ── ticketing's SQL against public.* ────────────────────────────────────────
def _iter_public_sql() -> list[tuple[str, str]]:
    """``[(relpath, sql), ...]`` — every SQL literal in ticketing/ naming a public table.

    Scoped to string arguments of ``text(...)``, walked from the AST. That is deliberate and
    load-bearing: ``text()`` is the only way raw SQL reaches the DB under SQLAlchemy 2.0, so
    this is "what actually executes" rather than "what mentions a table". No text-based
    filter can do this job — English prose says *"merge non-PII grievance fields **from
    public.grievances**"* (grievance_content.py:2) and *"TicketCreate **from
    public.grievances**"* (ticket_intake.py), which any FROM-anchored regex reads as SQL.
    Measured: scanning all string constants finds 13 "statements", 11 of which execute.

    Reading the AST also means ``#`` comments about ``public.file_attachments`` never
    register, and adjacent-literal concatenation (ticket_access.py) is folded for us.

    ``_PUBLIC_TABLE_RE`` then excludes pii_vault.py's ``text("SELECT pgp_sym_decrypt(...)")``:
    it is a bare function call against no table — a real ``text()`` call, but not a
    cross-schema read. A naive ``text(.*SELECT)`` scan would wrongly claim it as one.
    """
    found: list[tuple[str, str]] = []
    for path in sorted(TICKETING.rglob("*.py")):
        if MIGRATIONS in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name != "text":
                continue
            for arg in node.args:
                if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                    continue
                if _PUBLIC_TABLE_RE.search(arg.value):
                    found.append((str(path.relative_to(REPO_ROOT)), arg.value))
    return found


def _named_columns(sql: str, baseline: dict[str, set[str]]) -> tuple[set[str], set[str]]:
    """``(tables_touched, columns_named)`` for one statement.

    A "named column" is an identifier token that is a real column of one of the public
    tables this statement touches. Deriving it from the baseline instead of parsing SQL
    is what makes this robust: keywords, aliases (``g``/``gp``/``c``) and table names are
    not columns, so they cannot false-positive. Casts (``file_id::text``) and bind params
    (``:grievance_id``) are stripped first so type and param names don't leak in.
    """
    tables = set(_PUBLIC_TABLE_RE.findall(sql))
    stripped = re.sub(r"::\s*\w+", " ", sql)
    stripped = re.sub(r":\w+", " ", stripped)
    known: set[str] = set()
    for table in tables:
        known |= baseline.get(table, set())
    named = {tok for tok in _IDENT_RE.findall(stripped) if tok in known}
    return tables, named


@pytest.fixture(scope="module")
def statements() -> list[tuple[str, str]]:
    found = _iter_public_sql()
    # Guard the guard: a resolver that finds nothing must fail loudly, not pass vacuously.
    assert found, "scanner found no public.* SQL in ticketing/ — the scanner is broken"
    return found


# ── Rule 1 — the contract is closed, and it matches the code ────────────────
def test_statement_census_is_unchanged(statements):
    """§6 measured 11 statements. A new one is a boundary decision, not a detail."""
    assert len(statements) == EXPECTED_STATEMENT_COUNT, (
        f"expected {EXPECTED_STATEMENT_COUNT} public.* statements in ticketing/, "
        f"found {len(statements)}:\n"
        + "\n".join(f"  {p}: {s.strip().splitlines()[0][:70]}" for p, s in statements)
    )


def test_public_tables_touched_are_the_closed_set(statements, baseline):
    """No table outside CONTRACT. This is rule 1's enforcement."""
    touched: set[str] = set()
    for _, sql in statements:
        touched |= set(_PUBLIC_TABLE_RE.findall(sql))
    undeclared = sorted(touched - set(CONTRACT))
    assert not undeclared, (
        f"ticketing touches undeclared public.* tables: {undeclared}. "
        "Adding one is a deliberate decision — declare it in CONTRACT and in "
        "CLAUDE.md §Data rules rule 1, or route the access elsewhere."
    )


def test_every_named_column_is_declared(statements, baseline):
    """Code → contract. A column added to a select must be declared."""
    undeclared: list[str] = []
    for path, sql in statements:
        tables, named = _named_columns(sql, baseline)
        allowed: set[str] = set()
        for table in tables:
            allowed |= CONTRACT.get(table, set())
        for column in sorted(named - allowed):
            undeclared.append(f"{path}: {column} (tables={sorted(tables)})")
    assert not undeclared, "public.* columns named by ticketing but not in CONTRACT:\n" + "\n".join(
        undeclared
    )


def test_contract_has_no_stale_columns(statements, baseline):
    """Contract → code. A column no longer used must not linger in the contract."""
    named_anywhere: set[str] = set()
    for _, sql in statements:
        _, named = _named_columns(sql, baseline)
        named_anywhere |= named
    declared = {c for cols in CONTRACT.values() for c in cols}
    stale = sorted(declared - named_anywhere)
    assert not stale, (
        f"CONTRACT declares columns no ticketing statement names: {stale}. "
        "Drop them — a contract wider than the code overstates the coupling."
    )


def test_contract_columns_exist_in_public(baseline):
    """Contract → real schema. **This is the drift guard.**

    Absorbs the grievance_sync.py hardcoded-column-list TODO row: a public.* rename now
    fails here, naming the ticketing code that would have broken.
    """
    missing: list[str] = []
    for table, columns in CONTRACT.items():
        for column in sorted(columns - baseline[table]):
            missing.append(f"public.{table}.{column}")
    assert not missing, (
        f"ticketing selects public.* columns that no longer exist: {missing}. "
        "The chatbot schema moved under ticketing — fix the SQL and CONTRACT together."
    )


# ── Rule 2 — no cross-schema FK ─────────────────────────────────────────────
def _model_foreign_keys() -> list[tuple[str, str]]:
    import ticketing.models  # noqa: F401 — registers every model on Base.metadata
    from ticketing.models.base import Base

    return [
        (table.fullname, fk.target_fullname)
        for table in Base.metadata.tables.values()
        for fk in table.foreign_keys
    ]


def _migration_fk_targets() -> list[tuple[str, str]]:
    """FK target strings inside ForeignKey/ForeignKeyConstraint calls in the migrations.

    Read from the AST rather than the ORM: a migration can declare an FK that no model
    reflects, and Base.metadata would never see it.
    """
    targets: list[tuple[str, str]] = []
    for path in sorted(MIGRATIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in ("ForeignKey", "ForeignKeyConstraint"):
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    if "." in sub.value:
                        targets.append((path.name, sub.value))
    return targets


def test_no_cross_schema_foreign_keys_in_models():
    """Verified zero at 2026-07-15. Pins the invariant — not a bug fix.

    Rule 2 is the half of the March-2026 rule that survives: it is what actually preserves
    extraction optionality and keeps the three migration streams independent. Links to
    chatbot data are soft ``String(64)`` refs.
    """
    fks = _model_foreign_keys()
    assert fks, "no FKs found on Base.metadata — the resolver is broken, not the code"
    offenders = [f"{t} -> {target}" for t, target in fks if target.startswith("public.")]
    assert not offenders, f"cross-schema FK from ticketing.* into public.*: {offenders}"


def test_no_cross_schema_foreign_keys_in_migrations():
    """Same invariant, at the DDL stream that actually creates the constraints."""
    targets = _migration_fk_targets()
    assert targets, "no FK targets found in ticketing/migrations/versions — resolver broken"
    offenders = [f"{f}: {t}" for f, t in targets if t.startswith("public.")]
    assert not offenders, f"migration declares an FK into public.*: {offenders}"


# ── Rule 3 — complainant PII ────────────────────────────────────────────────
def test_no_complainant_pii_columns_in_ticketing_models():
    """Verified zero at 2026-07-15. Pins the invariant — not a bug fix.

    Reads Base.metadata, not the file text: ``services/demo_reveal.py`` holds these four
    names as in-memory demo-fixture dict keys, which is not a column and not a violation.
    """
    import ticketing.models  # noqa: F401
    from ticketing.models.base import Base

    tables = Base.metadata.tables
    assert tables, "no ticketing tables on Base.metadata — the resolver is broken"
    offenders = [
        f"{table.fullname}.{column.name}"
        for table in tables.values()
        for column in table.columns
        if column.name in PII_COLUMNS
    ]
    assert not offenders, f"complainant PII columns in ticketing.*: {offenders}"


def test_ticketing_declares_no_unexpected_complainant_columns():
    """Broader than the four names: the whole ``complainant_*`` namespace is fenced.

    Catches a future ``complainant_mobile``/``complainant_name`` that the exact-name check
    would wave through.
    """
    import ticketing.models  # noqa: F401
    from ticketing.models.base import Base

    offenders = [
        f"{table.fullname}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.name.startswith("complainant_")
        and column.name not in ALLOWED_COMPLAINANT_COLUMNS
    ]
    assert not offenders, (
        f"unexpected complainant_* columns in ticketing.*: {offenders}. "
        "Only an opaque complainant_id ref is allowed (CLAUDE.md §Data rules rule 3)."
    )


def test_public_complainants_is_not_a_pii_source(statements, baseline):
    """Rule 3's second half: ticketing may join complainants, but never for PII.

    grievance_sync.py's beat job LEFT JOINs public.complainants every 2 minutes and takes
    exactly one column — location_code. That is the line this test holds.
    """
    assert not (CONTRACT["complainants"] & PII_COLUMNS), "CONTRACT declares complainant PII"

    offenders: list[str] = []
    for path, sql in statements:
        _, named = _named_columns(sql, baseline)
        for column in sorted(named & PII_COLUMNS):
            offenders.append(f"{path}: {column}")
    assert not offenders, f"ticketing SQL selects complainant PII from public.*: {offenders}"


# ── guard the guards: prove the drift checks actually go red ────────────────
#
# The spec asks for a scratch-DB rename. That cannot work by construction: the guard reads
# the committed baseline *file*, so renaming a column in a scratch DB would not move it —
# the CL-01 CI gate is what catches DB-vs-baseline drift (see the module docstring's chain).
# So the mutation is applied where this guard actually reads, which is the standard T3-06
# set in D-28. Both directions, so neither check is vacuous.
def test_drift_guard_goes_red_when_public_renames_a_column(baseline):
    """Rename grievance_summary in the baseline ⇒ contract check must fail."""
    mutated = {t: set(c) for t, c in baseline.items()}
    mutated["grievances"].remove("grievance_summary")
    mutated["grievances"].add("grievance_summary_v2")

    missing = [
        f"public.{table}.{column}"
        for table, columns in CONTRACT.items()
        for column in sorted(columns - mutated[table])
    ]
    assert missing == ["public.grievances.grievance_summary"], (
        "the drift guard did not notice a renamed column — it is vacuous"
    )


def test_undeclared_column_guard_goes_red_on_a_new_select(baseline):
    """A statement naming a real-but-undeclared column must be caught."""
    sql = "SELECT grievance_id, is_temporary FROM public.grievances WHERE grievance_id = :gid"
    tables, named = _named_columns(sql, baseline)

    assert tables == {"grievances"}
    # is_temporary is a real public.grievances column no ticketing statement selects.
    assert "is_temporary" in named, "the column resolver missed a real column"
    assert named - CONTRACT["grievances"] == {"is_temporary"}


def test_column_resolver_ignores_keywords_aliases_and_params(baseline):
    """The resolver must not mistake SQL syntax for a column (that is how it false-positives)."""
    sql = """
        SELECT g.grievance_id, c.location_code AS location_code
        FROM public.grievances g
        LEFT JOIN public.complainants c ON g.complainant_id = c.complainant_id
        WHERE g.grievance_modification_date > :after_date
        ORDER BY g.grievance_id ASC LIMIT :limit
    """
    _, named = _named_columns(sql, baseline)
    assert named == {
        "grievance_id",
        "location_code",
        "complainant_id",
        "grievance_modification_date",
    }


# ── the doc is the policy, so pin the doc too ───────────────────────────────
#
# Added 2026-07-15 by the sprint's own devil's-advocate pass, which refuted a published
# claim. CLAUDE.md rule 1 says the contract is "Pinned by tests/ticketing/
# test_boundary_policy.py, which fails when the code and this list disagree". It was not:
# nothing here opened CLAUDE.md. What was pinned is code <-> CONTRACT (above); CLAUDE.md's
# table was a hand-maintained mirror kept in step by a *comment* ("keep them in step").
# Edit the table alone — add a table, flip a write — and all 13 guards still passed.
#
# That is a milder recurrence of exactly what §6 diagnosed: a rule whose enforcement is
# convention. And CLAUDE.md is where the rule actually lives for every human and agent on
# this repo — the CONTRACT dict is an implementation detail of the guard. Pinning the code
# to a dict nobody reads, while the document everybody reads drifts free, guards the wrong
# artifact. The chain is now closed: CLAUDE.md's table <-> CONTRACT <-> the code.

_CLAUDE_MD = REPO_ROOT / "CLAUDE.md"

# The rule-1 table: | `table` | access | where |
_RULE1_ROW_RE = re.compile(r"^\s*\|\s*`(\w+)`\s*\|([^|]*)\|", re.MULTILINE)


def _claude_md_rule1_table() -> dict[str, bool]:
    """Parse CLAUDE.md rule 1's table -> {table_name: declares_a_write}."""
    text = _CLAUDE_MD.read_text(encoding="utf-8")

    start = text.find("| `public.*` table | Ticketing's access | Where |")
    assert start != -1, (
        "CLAUDE.md rule 1's table header moved or was reworded — this guard cannot find "
        "it, and a guard that silently finds nothing is worse than no guard. Re-anchor it."
    )
    # The table ends at the first blank-ish line that is not a table row.
    end = text.find("\n\n", start)
    block = text[start:end if end != -1 else len(text)]

    rows: dict[str, bool] = {}
    for name, access in _RULE1_ROW_RE.findall(block):
        rows[name] = "write" in access.lower()
    return rows


def test_claude_md_rule1_table_matches_the_contract():
    """
    The table in CLAUDE.md must name exactly the tables CONTRACT allows. This is the claim
    CLAUDE.md makes about itself; now it is true.
    """
    documented = _claude_md_rule1_table()

    assert documented, "parsed zero rows out of CLAUDE.md rule 1 — the guard is vacuous"
    assert set(documented) == set(CONTRACT), (
        "CLAUDE.md rule 1's table and the CONTRACT set disagree.\n"
        f"  in CLAUDE.md but not CONTRACT: {sorted(set(documented) - set(CONTRACT))}\n"
        f"  in CONTRACT but not CLAUDE.md: {sorted(set(CONTRACT) - set(documented))}\n"
        "Adding a public.* table is a deliberate architectural decision — update the code, "
        "CONTRACT, and CLAUDE.md rule 1's table together, in the same commit."
    )


def test_claude_md_rule1_documents_exactly_the_three_writes(statements):
    """
    The 3 writes are the load-bearing detail of rule 1 — they are what makes it a
    read/write contract rather than a read one. Pin that the doc names the same tables the
    code actually writes, so a fourth write cannot land while the doc still says "read".
    """
    documented = _claude_md_rule1_table()
    doc_writes = {t for t, is_write in documented.items() if is_write}

    code_writes = {
        table
        for _site, sql in statements
        for table in _PUBLIC_TABLE_RE.findall(sql)
        if re.search(r"\b(UPDATE|INSERT|DELETE)\b", sql, re.IGNORECASE)
    }

    assert doc_writes == code_writes, (
        "CLAUDE.md rule 1 and the code disagree about which public.* tables ticketing WRITES.\n"
        f"  documented as written: {sorted(doc_writes)}\n"
        f"  actually written     : {sorted(code_writes)}\n"
        "A write to public.* that the doc calls a read is how the boundary rots quietly."
    )
