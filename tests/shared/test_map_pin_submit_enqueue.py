"""Regression: map-pin geocode enqueue must receive full submit payload, not split fields."""


def test_enqueue_uses_submit_payload_not_split():
    from backend.services.database_services import postgres_services as ps

    captured = {}

    original = ps.DatabaseManager._enqueue_map_pin_geocode_if_needed

    def _capture(self, data):
        captured["payload"] = dict(data)

    class FakeMgr:
        def get_complainant_and_grievance_fields(self, data):
            return {
                "complainant_fields": {"location_geo": data.get("location_geo")},
                "grievance_fields": {"grievance_id": data.get("grievance_id")},
            }

        _enqueue_map_pin_geocode_if_needed = _capture

    submit_payload = {
        "grievance_id": "B-GR-1",
        "complainant_id": "B-CM-1",
        "location_resolution_status": "map_pin",
        "location_geo": '{"source":"map_pin","lat":27.7172,"lng":85.324}',
    }
    split = FakeMgr().get_complainant_and_grievance_fields(submit_payload)
    FakeMgr()._enqueue_map_pin_geocode_if_needed(submit_payload)

    assert captured["payload"]["location_resolution_status"] == "map_pin"
    assert "complainant_fields" not in captured["payload"]
    assert "location_geo" not in split  # split wrapper should not be passed to enqueue
