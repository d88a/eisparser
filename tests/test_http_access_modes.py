from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import app as app_module
from api.routes import router as api_router
from api.routes.common import create_admin_token
from config.settings import settings


def _build_fake_pipeline():
    zakupka = SimpleNamespace(
        reg_number="test-001",
        description="test",
        initial_price=100.0,
        status="url_ready",
        prepared_at=None,
    )

    class FakeZakupkiRepo:
        def get_by_status(self, _status):
            return [zakupka]

        def get_status_counts(self):
            return {"raw": 1, "url_ready": 1}

    class FakeUserSelectionsRepo:
        def get_user_selections(self, _user_id):
            return []

    class FakeAI:
        def get_result(self, _reg_number):
            return None

    db = SimpleNamespace(
        zakupki=FakeZakupkiRepo(),
        user_selections=FakeUserSelectionsRepo(),
    )
    return SimpleNamespace(db=db, ai=FakeAI())


def _client_with_mode(monkeypatch, mode: str) -> TestClient:
    app = FastAPI()
    app.include_router(api_router)
    fake_pipeline = _build_fake_pipeline()
    monkeypatch.setattr(settings, "user_access_mode", mode)
    monkeypatch.setattr(app_module, "get_pipeline", lambda: fake_pipeline)
    return TestClient(app)


def test_public_user_api_allows_anonymous_and_admin_api_is_protected(monkeypatch):
    client = _client_with_mode(monkeypatch, "PUBLIC")

    user_resp = client.get("/api/user/available_zakupki")
    assert user_resp.status_code == 200, user_resp.text

    admin_resp = client.get("/api/admin/pipeline_status")
    assert admin_resp.status_code == 401, admin_resp.text


def test_auth_required_user_api_requires_auth(monkeypatch):
    client = _client_with_mode(monkeypatch, "AUTH_REQUIRED")
    resp = client.get("/api/user/available_zakupki")
    assert resp.status_code == 401, resp.text


def test_auth_required_user_api_and_admin_api_work_with_admin_cookie(monkeypatch):
    client = _client_with_mode(monkeypatch, "AUTH_REQUIRED")
    client.cookies.set("admin_token", create_admin_token())

    user_resp = client.get("/api/user/available_zakupki")
    assert user_resp.status_code == 200, user_resp.text

    admin_resp = client.get("/api/admin/pipeline_status")
    assert admin_resp.status_code == 200, admin_resp.text
