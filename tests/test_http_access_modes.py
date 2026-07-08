from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import app as app_module
from api.routes import router as api_router
from config.settings import settings


class FakeZakupkiRepo:
    def __init__(self):
        self.item = SimpleNamespace(
            reg_number="test-001",
            description="Тестовая закупка",
            initial_price=10_000_000,
            bid_end_date="2026-04-01",
            status="stage4_done",
            prepared_at=datetime(2026, 3, 20, 10, 0, 0),
            processed_at=datetime(2026, 3, 20, 11, 0, 0),
            update_date="2026-03-20",
        )

    def get_public_list_page(self, statuses, offset=0, limit=20):
        if self.item.status not in statuses:
            return [], 0
        row = {
            "reg_number": self.item.reg_number,
            "description": self.item.description,
            "bid_end_date": self.item.bid_end_date,
            "initial_price": self.item.initial_price,
            "status": self.item.status,
        }
        return [row][offset : offset + limit], 1

    def get_by_id(self, reg_number):
        return self.item if reg_number == self.item.reg_number else None

    def get_by_reg_numbers(self, reg_numbers):
        return [self.item] if self.item.reg_number in set(reg_numbers) else []


class FakeAIResultsRepo:
    def get_by_id(self, reg_number):
        if reg_number != "test-001":
            return None
        return SimpleNamespace(zakupka_name="Покупка квартиры")

    def get_by_reg_numbers_map(self, reg_numbers):
        return {"test-001": self.get_by_id("test-001")} if "test-001" in set(reg_numbers) else {}


class FakeListingsRepo:
    def get_for_zakupka(self, reg_number):
        if reg_number != "test-001":
            return []
        return [SimpleNamespace(price_rub=8_500_000, address="Екатеринбург")]

    def get_stats_for_zakupki(self, reg_numbers):
        out = {reg: {"listings_count": 0, "min_price_rub": None} for reg in reg_numbers}
        if "test-001" in out:
            out["test-001"] = {"listings_count": 1, "min_price_rub": 8_500_000}
        return out


class FakeListingReservationsRepo:
    def get_active_reserved_listing_ids_map(self, reg_numbers, expire=True):
        return {reg: set() for reg in reg_numbers}


class FakeUsersRepo:
    def __init__(self):
        self.items = {}
        self.seq = 1

    def get_by_email(self, email):
        return self.items.get((email or "").strip().lower())

    def create_public_user(self, email, password_hash):
        norm = (email or "").strip().lower()
        if not norm or norm in self.items:
            return None
        user = SimpleNamespace(id=self.seq, email=norm, role="public", password_hash=password_hash)
        self.items[norm] = user
        self.seq += 1
        return user


class FakeZakupkaReservationsRepo:
    ACTIVE = "active"

    def __init__(self):
        self.now = datetime(2026, 3, 26, 12, 0, tzinfo=timezone.utc)
        self.records = []

    def _expire(self):
        for rec in self.records:
            if rec["status"] == self.ACTIVE and rec["expires_at"] <= self.now:
                rec["status"] = "expired"

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
                "status": self.ACTIVE,
                "reserved_by": (reserved_by or "").strip().lower(),
                "expires_at": exp,
            }
        )
        return {"reg_number": reg_number, "expires_at": exp.isoformat(), "already_reserved": False}

    def get_active_page(self, offset=0, limit=20, reserved_by=None):
        self._expire()
        by = (reserved_by or "").strip().lower()
        active = [
            x
            for x in self.records
            if x["status"] == self.ACTIVE and (not by or x.get("reserved_by") == by)
        ]
        page = active[offset : offset + limit]
        return [{"reg_number": x["reg_number"], "expires_at": x["expires_at"].isoformat()} for x in page], len(active)

    def cancel_active(self, reg_number, reserved_by=None):
        self._expire()
        by = (reserved_by or "").strip().lower()
        changed = False
        for rec in self.records:
            if (
                rec["reg_number"] == reg_number
                and rec["status"] == self.ACTIVE
                and (not by or rec.get("reserved_by") == by)
            ):
                rec["status"] = "cancelled"
                changed = True
        return changed


def _client(monkeypatch):
    app = FastAPI()
    app.include_router(api_router)

    fake_db = SimpleNamespace(
        zakupki=FakeZakupkiRepo(),
        ai_results=FakeAIResultsRepo(),
        listings=FakeListingsRepo(),
        listing_reservations=FakeListingReservationsRepo(),
        zakupka_reservations=FakeZakupkaReservationsRepo(),
        users=FakeUsersRepo(),
    )
    fake_pipeline = SimpleNamespace(db=fake_db)

    monkeypatch.setattr(settings, "reservation_ttl_hours", 72)
    monkeypatch.setattr(settings, "user_access_mode", "PUBLIC")
    monkeypatch.setattr(app_module, "get_pipeline", lambda: fake_pipeline)

    return TestClient(app)


def test_guest_cannot_access_protected_public_endpoints(monkeypatch):
    client = _client(monkeypatch)

    reserve = client.post("/api/public/zakupki/test-001/reserve", json={})
    assert reserve.status_code == 401, reserve.text
    assert reserve.json()["detail"] == "Auth required"

    unreserve = client.post("/api/public/zakupki/test-001/unreserve")
    assert unreserve.status_code == 401, unreserve.text
    assert unreserve.json()["detail"] == "Auth required"

    html = client.get("/public/reservations", follow_redirects=False)
    assert html.status_code in (302, 307), html.text
    assert "/public/login?next=" in html.headers.get("location", "")


def test_register_reserve_only_own_reservations_and_logout(monkeypatch):
    client = _client(monkeypatch)

    reg = client.post(
        "/api/public/register",
        data={"email": "u1@example.com", "password": "StrongPass1", "password_confirm": "StrongPass1"},
        follow_redirects=False,
    )
    assert reg.status_code in (302, 303), reg.text
    assert "public_token" in reg.headers.get("set-cookie", ""), reg.headers

    reserve = client.post("/api/public/zakupki/test-001/reserve", json={})
    assert reserve.status_code == 200, reserve.text

    my_reservations = client.get("/api/public/reservations")
    assert my_reservations.status_code == 200, my_reservations.text
    assert my_reservations.json()["total"] == 1, my_reservations.text

    logout = client.post("/api/public/logout", follow_redirects=False)
    assert logout.status_code in (302, 303), logout.text

    login = client.post(
        "/api/public/login",
        data={"email": "u1@example.com", "password": "StrongPass1"},
        follow_redirects=False,
    )
    assert login.status_code in (302, 303), login.text
    assert "public_token" in login.headers.get("set-cookie", ""), login.headers

    after_login = client.get("/api/public/reservations")
    assert after_login.status_code == 200, after_login.text
    assert after_login.json()["total"] == 1, after_login.text

    logout = client.post("/api/public/logout", follow_redirects=False)
    assert logout.status_code in (302, 303), logout.text

    reg2 = client.post(
        "/api/public/register",
        data={"email": "u2@example.com", "password": "StrongPass2", "password_confirm": "StrongPass2"},
        follow_redirects=False,
    )
    assert reg2.status_code in (302, 303), reg2.text
    theirs = client.get("/api/public/reservations")
    assert theirs.status_code == 200, theirs.text
    assert theirs.json()["total"] == 0, theirs.text

    logout2 = client.post("/api/public/logout", follow_redirects=False)
    assert logout2.status_code in (302, 303), logout2.text

    after_logout = client.get("/api/public/reservations")
    assert after_logout.status_code == 401, after_logout.text
