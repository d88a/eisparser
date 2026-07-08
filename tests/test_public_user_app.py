from datetime import datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import app as app_module
from api.routes import router as api_router
from config.settings import settings


class FakeZakupkiRepo:
    def __init__(self):
        self._items = [
            SimpleNamespace(
                reg_number="test-001",
                description="Тестовая закупка 1",
                initial_price=10_000_000,
                bid_end_date="2026-04-01",
                status="stage4_done",
                prepared_at=datetime(2026, 3, 20, 10, 0, 0),
                processed_at=datetime(2026, 3, 20, 11, 0, 0),
                two_gis_url="https://2gis.ru/hidden",
                update_date="2026-03-20",
            ),
            SimpleNamespace(
                reg_number="test-002",
                description="Тестовая закупка 2",
                initial_price=12_000_000,
                bid_end_date="2026-04-02",
                status="stage4_done",
                prepared_at=datetime(2026, 3, 20, 9, 0, 0),
                processed_at=datetime(2026, 3, 20, 10, 0, 0),
                two_gis_url="https://2gis.ru/hidden2",
                update_date="2026-03-20",
            ),
        ]

    def get_by_statuses(self, _statuses):
        return list(self._items)

    def get_by_id(self, reg_number):
        for item in self._items:
            if item.reg_number == reg_number:
                return item
        return None


class FakeAIResultsRepo:
    def get_by_id(self, reg_number):
        if reg_number != "test-001":
            return None
        return SimpleNamespace(
            zakupka_name="Покупка квартиры",
            city="Екатеринбург",
            address="ул. Ленина, 1",
            area_min_m2=32.0,
            area_max_m2=48.0,
            rooms="1-2",
            floor="2",
            building_floors_min="9",
            year_build_str="2015",
            wear_percent=5.0,
            zakazchik='МКУ "УКС"',
        )


class FakeListingsRepo:
    def get_for_zakupka(self, reg_number):
        if reg_number != "test-001":
            return []
        return [
            SimpleNamespace(
                address="Екатеринбург, ул. Ленина, 10",
                price_rub=8_100_000,
                area_m2=41.2,
                rooms=1,
                floor=3,
                building_floors=12,
                building_year=2017,
                two_gis_url="https://2gis.ru/private-item",
                external_source="cian",
                external_url="https://www.cian.ru/example",
            )
        ]


def _client(monkeypatch, mode="PUBLIC"):
    app = FastAPI()
    app.include_router(api_router)

    fake_db = SimpleNamespace(
        zakupki=FakeZakupkiRepo(),
        ai_results=FakeAIResultsRepo(),
        listings=FakeListingsRepo(),
    )
    fake_pipeline = SimpleNamespace(db=fake_db)

    monkeypatch.setattr(settings, "user_access_mode", mode)
    monkeypatch.setattr(app_module, "get_pipeline", lambda: fake_pipeline)

    return TestClient(app)


def test_public_api_list_and_detail_hide_two_gis(monkeypatch):
    client = _client(monkeypatch)

    list_resp = client.get("/api/public/zakupki")
    assert list_resp.status_code == 200, list_resp.text
    payload = list_resp.json()
    assert payload["items"], payload
    first = payload["items"][0]
    assert "two_gis_url" not in first, first
    labels = {x["reg_number"]: x["status_label"] for x in payload["items"]}
    assert labels["test-001"] == "Есть варианты квартир", labels
    assert labels["test-002"] == "Нет вариантов квартир", labels

    detail_resp = client.get("/api/public/zakupki/test-001")
    assert detail_resp.status_code == 200, detail_resp.text
    detail = detail_resp.json()
    assert detail["reg_number"] == "test-001", detail
    assert "two_gis_url" not in detail, detail
    assert detail["listings"], detail
    assert "two_gis_url" not in detail["listings"][0], detail["listings"][0]


def test_public_html_pages_available(monkeypatch):
    client = _client(monkeypatch)

    list_page = client.get("/public/zakupki")
    assert list_page.status_code == 200, list_page.text
    assert "Список закупок" in list_page.text, list_page.text

    detail_page = client.get("/public/zakupki/test-001")
    assert detail_page.status_code == 200, detail_page.text
    assert "Характеристики закупки" in detail_page.text, detail_page.text


def test_public_api_stays_open_in_auth_required_mode(monkeypatch):
    client = _client(monkeypatch, mode="AUTH_REQUIRED")

    list_resp = client.get("/api/public/zakupki")
    assert list_resp.status_code == 200, list_resp.text

    detail_resp = client.get("/api/public/zakupki/test-001")
    assert detail_resp.status_code == 200, detail_resp.text
