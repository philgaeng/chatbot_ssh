from backend.shared_functions.location_mapping import resolve_location_payload


class _DbStub:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def execute_query(self, query, params, operation=None):
        result = self.responses[self.calls] if self.calls < len(self.responses) else []
        self.calls += 1
        return result


def test_resolve_location_payload_mapped_full():
    db = _DbStub(
        [
            [{"location_code": "NP_P1"}],
            [{"location_code": "NP_D001"}],
            [{"location_code": "NP_M0001"}],
        ]
    )
    payload = resolve_location_payload(
        db,
        {
            "complainant_province": "Koshi Province",
            "complainant_district": "Bhojpur",
            "complainant_municipality": "Bhojpur Municipality",
        },
    )
    assert payload["location_code"] == "NP_M0001"
    assert payload["location_resolution_status"] == "mapped_full"
    assert payload["level_3_code"] == "NP_M0001"


def test_resolve_location_payload_mapped_partial():
    db = _DbStub([[{"location_code": "NP_P1"}], []])
    payload = resolve_location_payload(
        db,
        {"complainant_province": "Koshi Province", "complainant_district": "Unknown"},
    )
    assert payload["location_code"] == "NP_P1"
    assert payload["location_resolution_status"] == "mapped_partial"
    assert payload["level_1_code"] == "NP_P1"
    assert payload["level_2_code"] is None


def test_resolve_location_payload_free_text_only_on_error():
    class _ErrorDb:
        def execute_query(self, *args, **kwargs):
            raise RuntimeError("lookup failed")

    payload = resolve_location_payload(
        _ErrorDb(),
        {"complainant_province": "Koshi Province"},
    )
    assert payload["location_code"] is None
    assert payload["location_resolution_status"] == "free_text_only"
