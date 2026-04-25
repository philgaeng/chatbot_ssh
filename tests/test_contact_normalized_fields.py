from backend.services.database_services.base_manager import BaseDatabaseManager
from backend.services.database_services.complainant_manager import ComplainantDbManager


class _NoopLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


def _build_complainant_manager() -> ComplainantDbManager:
    mgr = ComplainantDbManager.__new__(ComplainantDbManager)
    mgr.logger = _NoopLogger()
    mgr.encryption_key = None
    mgr.generate_id = lambda *_args, **_kwargs: "CM-TEST-1"
    mgr._standardize_phone_number = lambda phone: phone
    mgr._encrypt_and_hash_sensitive_data = lambda data: data
    return mgr


def test_base_manager_routes_normalized_contact_fields_to_complainant():
    manager = BaseDatabaseManager.__new__(BaseDatabaseManager)
    payload = {
        "complainant_id": "CM-1",
        "grievance_id": "GR-1",
        "complainant_full_name": "Name",
        "contact_id": "contact-1",
        "country_code": "NP",
        "location_code": "NP_M0001",
        "location_resolution_status": "mapped_full",
        "level_1_name": "Koshi",
        "level_1_code": "NP_P1",
        "grievance_description": "Some grievance",
    }

    split = manager.get_complainant_and_grievance_fields(payload)

    complainant_fields = split["complainant_fields"]
    grievance_fields = split["grievance_fields"]

    assert complainant_fields["contact_id"] == "contact-1"
    assert complainant_fields["country_code"] == "NP"
    assert complainant_fields["location_code"] == "NP_M0001"
    assert complainant_fields["level_1_code"] == "NP_P1"
    assert "contact_id" not in grievance_fields
    assert grievance_fields["grievance_id"] == "GR-1"


def test_complainant_allowed_update_fields_include_normalized_columns():
    required = {
        "contact_id",
        "country_code",
        "location_code",
        "location_resolution_status",
        "level_1_name",
        "level_6_name",
        "level_1_code",
        "level_6_code",
    }
    assert required.issubset(ComplainantDbManager.ALLOWED_UPDATE_FIELDS)


def test_create_complainant_accepts_normalized_columns():
    manager = _build_complainant_manager()
    captured = {}

    def _capture_insert(table_name, input_data, allowed_fields=None, **_kwargs):
        captured["table_name"] = table_name
        captured["input_data"] = input_data
        captured["allowed_fields"] = allowed_fields
        return True

    manager.execute_insert = _capture_insert

    payload = {
        "complainant_full_name": "Tester",
        "complainant_phone": "+9779800000000",
        "contact_id": "contact-22",
        "country_code": "NP",
        "location_code": "NP_M0001",
        "location_resolution_status": "mapped_partial",
        "level_3_name": "Bhojpur Municipality",
        "level_3_code": "NP_M0001",
    }
    assert manager.create_complainant(payload) is True
    assert captured["table_name"] == "complainants"
    assert captured["input_data"]["contact_id"] == "contact-22"
    assert captured["input_data"]["location_code"] == "NP_M0001"
    assert "contact_id" in captured["input_data"]
    assert "level_3_code" in captured["input_data"]


def test_update_complainant_accepts_normalized_columns():
    manager = _build_complainant_manager()
    captured = {}

    def _capture_update(query, values, *_args, **_kwargs):
        captured["query"] = query
        captured["values"] = values
        return 1

    manager.execute_update = _capture_update

    affected = manager.update_complainant(
        "CM-123",
        {
            "contact_id": "contact-99",
            "country_code": "NP",
            "location_code": "NP_D001",
            "level_2_code": "NP_D001",
        },
    )
    assert affected == 1
    assert "contact_id = %s" in captured["query"]
    assert "location_code = %s" in captured["query"]
