from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import app as app_module
from api.routes import router as api_router
from api.routes.common import create_public_token
from config.settings import settings


class FakeZakupkiRepo:
    def __init__(self):
        self.items = {
            "test-001": SimpleNamespace(
                reg_number="test-001",
                description="Тестовая закупка",
                initial_price=10_000_000,
                bid_end_date="2026-04-01",
                status="stage4_done",
                prepared_at=datetime(2026, 3, 20, 10, 0, 0),
                processed_at=datetime(2026, 3, 20, 11, 0, 0),
                update_date="2026-03-20",
            ),
            "test-002": SimpleNamespace(
                reg_number="test-002",
                description="Тестовая закупка 2",
                initial_price=12_000_000,
                bid_end_date="2026-04-10",
                status="stage4_done",
                prepared_at=datetime(2026, 3, 21, 10, 0, 0),
                processed_at=datetime(2026, 3, 21, 11, 0, 0),
                update_date="2026-03-21",
            ),
        }

    def get_public_list_page(self, statuses, offset=0, limit=20):
        rows = []
        for item in self.items.values():
            if item.status in statuses:
                rows.append(
                    {
                        "reg_number": item.reg_number,
                        "description": item.description,
                        "bid_end_date": item.bid_end_date,
                        "initial_price": item.initial_price,
                        "status": item.status,
                    }
                )
        return rows[offset : offset + limit], len(rows)

    def get_by_id(self, reg_number):
        return self.items.get(reg_number)

    def get_by_reg_numbers(self, reg_numbers):
        regs = set(reg_numbers)
        return [x for k, x in self.items.items() if k in regs]


class FakeAIResultsRepo:
    def get_by_id(self, reg_number):
        if reg_number == "test-001":
            return SimpleNamespace(zakupka_name="Покупка квартиры", city="Екатеринбург")
        return None

    def get_by_reg_numbers_map(self, reg_numbers):
        return {reg: self.get_by_id(reg) for reg in reg_numbers if self.get_by_id(reg)}


class FakeListingsRepo:
    def get_for_zakupka(self, reg_number):
        if reg_number == "test-001":
            return [SimpleNamespace(price_rub=8_500_000, address="Екатеринбург")]
        if reg_number == "test-002":
            return [SimpleNamespace(price_rub=9_000_000, address="Екатеринбург")]
        return []

    def get_stats_for_zakupki(self, reg_numbers):
        out = {reg: {"listings_count": 0, "min_price_rub": None} for reg in reg_numbers}
        if "test-001" in out:
            out["test-001"] = {"listings_count": 1, "min_price_rub": 8_500_000}
        if "test-002" in out:
            out["test-002"] = {"listings_count": 1, "min_price_rub": 9_000_000}
        return out


class FakeListingReservationsRepo:
    def get_active_reserved_listing_ids_map(self, reg_numbers, expire=True):
        return {reg: set() for reg in reg_numbers}


class FakePublicFavoritesRepo:
    def __init__(self):
        self.rows = []

    def add_favorite(self, reg_number, user_email):
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        if not reg or not email:
            return False
        for row in self.rows:
            if row["reg_number"] == reg and row["user_email"] == email:
                return True
        self.rows.append(
            {
                "reg_number": reg,
                "user_email": email,
                "created_at": datetime(2026, 3, 26, 12, 30, tzinfo=timezone.utc).isoformat(),
            }
        )
        return True

    def remove_favorite(self, reg_number, user_email):
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        before = len(self.rows)
        self.rows = [x for x in self.rows if not (x["reg_number"] == reg and x["user_email"] == email)]
        return len(self.rows) < before

    def is_favorite(self, reg_number, user_email):
        reg = (reg_number or "").strip()
        email = (user_email or "").strip().lower()
        return any(x["reg_number"] == reg and x["user_email"] == email for x in self.rows)

    def get_favorite_reg_numbers_map(self, reg_numbers, user_email):
        regs = set(reg_numbers)
        email = (user_email or "").strip().lower()
        mine = {x["reg_number"] for x in self.rows if x["user_email"] == email}
        return {reg: reg in mine for reg in regs}

    def get_favorites_page(self, user_email, offset=0, limit=20):
        email = (user_email or "").strip().lower()
        mine = [x for x in self.rows if x["user_email"] == email]
        return mine[offset : offset + limit], len(mine)


class FakeZakupkaReservationsRepo:
    ACTIVE = "active"

    def __init__(self):
        self.now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
        self.records = []

    def _expire(self):
        for rec in self.records:
            if rec["status"] == self.ACTIVE and rec["expires_at"] <= self.now:
                rec["status"] = "expired"
                rec["end_reason"] = "expired"
                rec["updated_at"] = self.now.isoformat()

    def get_active_reservations_map(self, reg_numbers, now=None, expire=True):
        if now is not None:
            self.now = now
        if expire:
            self._expire()
        targets = set(reg_numbers)
        out = {}
        for rec in self.records:
            if rec["status"] == self.ACTIVE and rec["reg_number"] in targets and rec["reg_number"] not in out:
                out[rec["reg_number"]] = rec["expires_at"].isoformat()
        return out

    def reserve_procurement(self, reg_number, reserved_by, ttl_hours, now=None):
        if now is not None:
            self.now = now
        self._expire()
        active = self.get_active_reservations_map([reg_number], expire=False)
        if reg_number in active:
            return {"reg_number": reg_number, "expires_at": active[reg_number], "already_reserved": True}
        exp = self.now + timedelta(hours=max(1, int(ttl_hours)))
        self.records.append(
            {
                "reg_number": reg_number,
                "reserved_by": (reserved_by or "").strip().lower(),
                "status": self.ACTIVE,
                "expires_at": exp,
                "updated_at": self.now.isoformat(),
                "end_reason": None,
            }
        )
        return {"reg_number": reg_number, "expires_at": exp.isoformat(), "already_reserved": False}

    def get_active_page(self, offset=0, limit=20, reserved_by=None):
        self._expire()
        by = (reserved_by or "").strip().lower()
        active = [x for x in self.records if x["status"] == self.ACTIVE and (not by or x["reserved_by"] == by)]
        page = active[offset : offset + limit]
        return [
            {
                "reg_number": x["reg_number"],
                "expires_at": x["expires_at"].isoformat(),
                "updated_at": x["updated_at"],
                "end_reason": x["end_reason"],
            }
            for x in page
        ], len(active)

    def get_history_page(self, user_email, offset=0, limit=20):
        self._expire()
        by = (user_email or "").strip().lower()
        rows = [x for x in self.records if x["status"] != self.ACTIVE and x["reserved_by"] == by]
        page = rows[offset : offset + limit]
        return [
            {
                "reg_number": x["reg_number"],
                "expires_at": x["expires_at"].isoformat(),
                "updated_at": x["updated_at"],
                "end_reason": x["end_reason"] or "other",
            }
            for x in page
        ], len(rows)

    def cancel_active(self, reg_number, reserved_by=None):
        self._expire()
        by = (reserved_by or "").strip().lower()
        for rec in self.records:
            if rec["reg_number"] == reg_number and rec["status"] == self.ACTIVE and rec["reserved_by"] == by:
                rec["status"] = "cancelled"
                rec["end_reason"] = "manual_unreserve"
                rec["updated_at"] = self.now.isoformat()
                return True
        return False


class FakeUsersRepo:
    def get_by_email(self, email):
        return SimpleNamespace(id=1, email=email, role="public", password_hash="x")


def _client(monkeypatch, auth_email="u1@example.com", with_auth=True):
    app = FastAPI()
    app.include_router(api_router)

    fake_db = SimpleNamespace(
        zakupki=FakeZakupkiRepo(),
        ai_results=FakeAIResultsRepo(),
        listings=FakeListingsRepo(),
        listing_reservations=FakeListingReservationsRepo(),
        zakupka_reservations=FakeZakupkaReservationsRepo(),
        public_favorites=FakePublicFavoritesRepo(),
        users=FakeUsersRepo(),
    )
    fake_pipeline = SimpleNamespace(db=fake_db)

    monkeypatch.setattr(settings, "reservation_ttl_hours", 72)
    monkeypatch.setattr(settings, "user_access_mode", "PUBLIC")
    monkeypatch.setattr(app_module, "get_pipeline", lambda: fake_pipeline)

    client = TestClient(app)
    if with_auth:
        client.cookies.set("public_token", create_public_token(1, auth_email))
    return client


def test_active_reservations_only_for_current_user(monkeypatch):
    client = _client(monkeypatch, auth_email="u1@example.com")
    client.post("/api/public/zakupki/test-001/reserve", json={})

    client.cookies.set("public_token", create_public_token(2, "u2@example.com"))
    active_other = client.get("/api/public/reservations?tab=active").json()
    assert active_other["total"] == 0, active_other

    client.cookies.set("public_token", create_public_token(1, "u1@example.com"))
    active_mine = client.get("/api/public/reservations?tab=active").json()
    assert active_mine["total"] == 1, active_mine


def test_unreserve_moves_to_history(monkeypatch):
    client = _client(monkeypatch, auth_email="u1@example.com")
    client.post("/api/public/zakupki/test-001/reserve", json={})

    unreserve = client.post("/api/public/zakupki/test-001/unreserve")
    assert unreserve.status_code == 200, unreserve.text

    active = client.get("/api/public/reservations?tab=active").json()
    assert active["total"] == 0, active

    history = client.get("/api/public/reservations?tab=history").json()
    assert history["total"] == 1, history
    assert history["items"][0]["end_reason"] == "manual_unreserve", history


def test_favorites_create_delete_and_visible_only_for_owner(monkeypatch):
    client = _client(monkeypatch, auth_email="u1@example.com")

    add = client.post("/api/public/zakupki/test-001/favorite")
    assert add.status_code == 200, add.text

    mine = client.get("/api/public/favorites").json()
    assert mine["total"] == 1, mine
    assert mine["items"][0]["reg_number"] == "test-001", mine

    other = _client(monkeypatch, auth_email="u2@example.com")
    theirs = other.get("/api/public/favorites").json()
    assert theirs["total"] == 0, theirs

    remove = client.post("/api/public/zakupki/test-001/unfavorite")
    assert remove.status_code == 200, remove.text

    empty = client.get("/api/public/favorites").json()
    assert empty["total"] == 0, empty


def test_guest_gets_401_for_favorites_and_history(monkeypatch):
    client = _client(monkeypatch, with_auth=False)

    favorites = client.get("/api/public/favorites")
    assert favorites.status_code == 401, favorites.text
    assert favorites.json()["detail"] == "Auth required"

    history = client.get("/api/public/reservations?tab=history")
    assert history.status_code == 401, history.text
    assert history.json()["detail"] == "Auth required"


def test_reserve_still_works_idempotent(monkeypatch):
    client = _client(monkeypatch, auth_email="u1@example.com")

    first = client.post("/api/public/zakupki/test-001/reserve", json={})
    assert first.status_code == 200, first.text
    assert first.json()["already_reserved"] is False

    second = client.post("/api/public/zakupki/test-001/reserve", json={})
    assert second.status_code == 200, second.text
    assert second.json()["already_reserved"] is True
