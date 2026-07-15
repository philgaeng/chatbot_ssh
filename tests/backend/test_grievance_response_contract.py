"""
T3-06 step 1 — response contract for GET /api/grievance/{id}.

The endpoint had no ``response_model``: the payload was whatever ``SELECT g.*``
plus the complainant/party join returned, passed through verbatim. ``GrievanceRecord``
now pins that shape.

The drift gate reads ``migrations/public/expected_public_schema.sql`` — the CL-01
canonical baseline that CI already asserts equals the freshly-migrated public schema
(``scripts/ci/check_public_schema_baseline.sh``). Parsing it keeps these tests
DB-free while still being pinned to real DDL.
"""

import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.fastapi_app import app
from backend.api.routers.grievance import GrievanceRecord

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_SQL = REPO_ROOT / "migrations" / "public" / "expected_public_schema.sql"

# The join behind get_grievance_by_id (grievance_manager.py:154-167).
GRIEVANCE_TABLE = "grievances"
JOINED_TABLES = ("complainants", "grievance_parties")

# The 9 fields ticketing/services/grievance_content.py selects. Load-bearing:
# dropping one from the model silently drops it from the API response.
LOAD_BEARING_FIELDS = (
    "grievance_id",
    "grievance_summary",
    "grievance_categories",
    "grievance_description",
    "grievance_location",
    "grievance_classification_status",
    "grievance_high_priority",
    "grievance_sensitive_issue",
    "grievance_modification_date",
)

_CREATE_TABLE_RE = re.compile(
    r"CREATE TABLE public\.(\w+) \((.*?)\n\);", re.DOTALL
)
# Lines that are table constraints rather than columns.
_NON_COLUMN_PREFIX = ("CONSTRAINT", "PRIMARY", "UNIQUE", "CHECK", "FOREIGN", "EXCLUDE")


def _parse_baseline_columns() -> dict[str, set[str]]:
    """{table: {column, ...}} from the committed pg_dump baseline."""
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
    # Guard the parser itself: a silently-empty parse would make every
    # assertion below vacuous.
    for table in (GRIEVANCE_TABLE, *JOINED_TABLES):
        assert tables.get(table), f"parsed no columns for public.{table}"
    return tables


def test_load_bearing_fields_are_declared_on_the_model():
    """The 9 fields grievance_content.py depends on must survive serialization."""
    declared = set(GrievanceRecord.model_fields)
    missing = [f for f in LOAD_BEARING_FIELDS if f not in declared]
    assert not missing, f"load-bearing fields dropped from GrievanceRecord: {missing}"


def test_load_bearing_fields_exist_in_public_grievances(baseline):
    missing = [f for f in LOAD_BEARING_FIELDS if f not in baseline[GRIEVANCE_TABLE]]
    assert not missing, f"fields absent from public.grievances: {missing}"


def test_every_model_field_exists_in_the_public_schema(baseline):
    """No field on the model that the query cannot produce (typo / dropped column)."""
    available = set(baseline[GRIEVANCE_TABLE])
    for table in JOINED_TABLES:
        available |= baseline[table]

    unknown = sorted(set(GrievanceRecord.model_fields) - available)
    assert not unknown, (
        "GrievanceRecord declares fields absent from public.grievances/"
        f"complainants/grievance_parties: {unknown}"
    )


def test_model_covers_every_grievances_column(baseline):
    """
    SELECT g.* means a new public.grievances column lands in the response
    automatically (extra='allow' passes it through, so this is a documentation
    gate, not a breakage gate). Declare the column on GrievanceRecord.
    """
    undeclared = sorted(baseline[GRIEVANCE_TABLE] - set(GrievanceRecord.model_fields))
    assert not undeclared, (
        "public.grievances columns not declared on GrievanceRecord "
        f"(SELECT g.* returns them undocumented): {undeclared}"
    )


def test_response_model_does_not_drop_undeclared_columns():
    """
    extra='allow' is load-bearing. Under the default (extra='ignore') a column
    absent from the model is silently stripped from the response — the exact
    failure the ticket warns about. Pin the behaviour.
    """
    record = GrievanceRecord.model_validate(
        {"grievance_id": "B-GR-TEST", "column_added_later": "must-survive"}
    )
    assert record.model_dump()["column_added_later"] == "must-survive"


def test_json_parsed_text_columns_do_not_break_validation():
    """
    _parse_field_from_database json.loads every string column, so TEXT values
    reach the model as list/int (grievance_categories is a list in practice; a
    summary of "2024" becomes an int). Typing these as str would 500 on real data.
    """
    record = GrievanceRecord.model_validate(
        {
            "grievance_id": "B-GR-TEST",
            "grievance_categories": ["Environmental - Air Pollution"],
            "follow_up_question": ["How many people?"],
            "grievance_summary": 2024,
            "complainant_ward": 5,
        }
    )
    dumped = record.model_dump()
    assert dumped["grievance_categories"] == ["Environmental - Air Pollution"]
    assert dumped["grievance_summary"] == 2024
    assert dumped["complainant_ward"] == 5


def test_openapi_documents_the_grievance_response():
    """The contract is visible to callers, not just enforced at runtime."""
    schema = app.openapi()
    responses = schema["paths"]["/api/grievance/{grievance_id}"]["get"]["responses"]
    ref = responses["200"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("GrievanceDetailResponse")


def test_get_grievance_404_is_unchanged_by_the_response_model():
    """
    The 404 path returns JSONResponse, which bypasses response_model validation.
    Commit 1 must stay inert.
    """
    client = TestClient(app)
    # The GET requires x-api-key since T3-06 step 3; pin and send one so this
    # asserts the 404 contract rather than auth.
    with patch.dict("os.environ", {"TICKETING_SECRET_KEY": "contract-key"}):
        r = client.get(
            "/api/grievance/nonexistent-id-12345",
            headers={"x-api-key": "contract-key"},
        )
    assert r.status_code == 404
    assert r.json()["status"] == "ERROR"
