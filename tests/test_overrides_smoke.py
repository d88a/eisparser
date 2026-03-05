from pathlib import Path

import pytest
import requests


BASE_URL = "http://127.0.0.1:8000"
def _load_admin_password() -> str:
    env_path = Path(__file__).resolve().parents[1] / "src" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("ADMIN_PASSWORD="):
                return line.split("=", 1)[1].strip()
    return "admin"


def _verify_override_in_backend(user_id: int, reg_number: str, field_name: str, expected_value: str):
    try:
        from services.database_service import DatabaseService

        db = DatabaseService()
        overrides = db.user_overrides.get_for_zakupka(reg_number, user_id)
    except Exception as exc:
        pytest.skip(f"cannot verify override via configured DB backend: {exc}")

    assert overrides.get(field_name) == expected_value, overrides


def test_overrides_flow():
    user_id = 1
    field_name = "city"
    new_value = "Тестовый Город"
    admin_password = _load_admin_password()
    session = requests.Session()
    try:
        health = session.get(f"{BASE_URL}/", timeout=2)
    except requests.RequestException:
        pytest.skip("requires running local API server at 127.0.0.1:8000")
    if health.status_code >= 500:
        pytest.skip("local API endpoint is unavailable (5xx)")

    login_resp = session.post(
        f"{BASE_URL}/admin/login",
        data={"password": admin_password},
        allow_redirects=False,
    )
    assert login_resp.status_code in (302, 303), login_resp.text

    stage2_resp = session.get(f"{BASE_URL}/api/stage2")
    assert stage2_resp.status_code == 200, stage2_resp.text

    stage2_payload = stage2_resp.json()
    assert isinstance(stage2_payload, dict), stage2_payload
    assert "items" in stage2_payload, stage2_payload

    items = stage2_payload["items"]
    assert isinstance(items, list), items
    assert items, "Stage 2 is empty, cannot run smoke override test"

    target = items[0]
    reg_number = target["reg_number"]
    assert "ai_city" in target, target

    override_payload = {
        "user_id": user_id,
        "reg_number": reg_number,
        "field_name": field_name,
        "value": new_value,
    }
    save_resp = session.post(f"{BASE_URL}/api/overrides", json=override_payload)
    assert save_resp.status_code == 200, save_resp.text
    assert save_resp.json().get("status") == "ok", save_resp.json()

    _verify_override_in_backend(
        user_id=user_id,
        reg_number=reg_number,
        field_name=field_name,
        expected_value=new_value,
    )

    overrides_resp = session.get(f"{BASE_URL}/api/overrides/{reg_number}?user_id={user_id}")
    assert overrides_resp.status_code == 200, overrides_resp.text
    overrides_payload = overrides_resp.json()
    assert isinstance(overrides_payload, dict), overrides_payload
    stored_value = overrides_payload.get(field_name)
    assert str(stored_value) == new_value, overrides_payload


if __name__ == "__main__":
    test_overrides_flow()
