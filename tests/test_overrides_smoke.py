import sqlite3
from pathlib import Path

import requests


BASE_URL = "http://127.0.0.1:8000"
DB_PATH = "D:/Anna/eisparser/results/eis_data.db"


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


def test_overrides_flow():
    user_id = 1
    field_name = "city"
    new_value = "Тестовый Город"
    admin_password = _load_admin_password()
    session = requests.Session()

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

    with sqlite3.connect(DB_PATH) as con:
        row = con.execute(
            """
            SELECT value
            FROM user_overrides
            WHERE user_id = ? AND reg_number = ? AND field_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, reg_number, field_name),
        ).fetchone()
    assert row is not None, "Override row not found in DB"
    assert row[0] == new_value, row

    overrides_resp = session.get(f"{BASE_URL}/api/overrides/{reg_number}?user_id={user_id}")
    assert overrides_resp.status_code == 200, overrides_resp.text
    overrides_payload = overrides_resp.json()
    assert isinstance(overrides_payload, dict), overrides_payload
    stored_value = overrides_payload.get(field_name)
    assert str(stored_value) == new_value, overrides_payload


if __name__ == "__main__":
    test_overrides_flow()
