"""Service for assembling UI/public view models."""

from datetime import datetime
from dataclasses import asdict
import re
from typing import List, Optional

from models.statuses import ZakupkaStatus
from models.view_models import PublicListingView, PublicZakupkaDetail, PublicZakupkaListItem, ZakupkaStageView
from services.database_service import DatabaseService
from utils.logger import get_logger


class ViewService:
    """Service for aggregating database entities into read-only view models."""

    def __init__(self, db_service: DatabaseService):
        self.db = db_service
        self.logger = get_logger("ViewService")

    @staticmethod
    def _is_garbled_text(value: Optional[str]) -> bool:
        raw = str(value or "").strip()
        if not raw:
            return True
        if "\uFFFD" in raw:
            return True
        q_count = raw.count("?")
        if q_count >= 4 and (q_count / max(1, len(raw))) >= 0.2:
            return True
        has_cyrillic = re.search(r"[А-Яа-яЁё]", raw) is not None
        if not has_cyrillic and q_count >= 6:
            return True
        return False

    @staticmethod
    def _looks_like_noisy_title(value: Optional[str]) -> bool:
        raw = str(value or "").strip()
        if not raw:
            return True

        lowered = raw.lower()
        if len(raw) > 420:
            return True
        if "document:" in lowered or "===" in lowered:
            return True
        if "обоснование" in lowered and len(raw) > 180:
            return True
        if raw.count("\n") >= 3:
            return True
        if raw.count(",") >= 14:
            return True
        if len(re.findall(r"\bул\.", lowered)) >= 4:
            return True
        return False

    @classmethod
    def _pick_public_title(cls, ai_title: Optional[str], fallback_title: Optional[str], reg_number: Optional[str] = None) -> str:
        candidate = re.sub(r"\s+", " ", str(ai_title or "")).strip()
        fallback = re.sub(r"\s+", " ", str(fallback_title or "")).strip()
        chosen = ""

        # Убираем типовые числовые префиксы в начале названия:
        # "33-0015-11575 - 2026 ...", "12345: ...", "001-02-03 - ...".
        prefix_patterns = [
            r"^\s*[0-9A-Za-zА-Яа-яЁё]{1,8}(?:[-–][0-9A-Za-zА-Яа-яЁё]{1,8}){1,5}\s*[-:]\s*\d{4}\s*[-:]?\s*",
            r"^\s*\d{2,6}(?:[-–]\d{2,6}){1,5}\s*[-:]\s*\d{4}\s*[-:]?\s*",
            r"^\s*\d{2,6}(?:[-–]\d{2,6}){1,5}\s*[-:]\s*",
            r"^\s*\d{4}\s*[-?:]\s*",
            r"^\s*\d{2,6}\s*[-?:]\s*",
        ]

        def _clean(value: str) -> str:
            cleaned = value
            for _ in range(3):
                before = cleaned
                for pattern in prefix_patterns:
                    cleaned = re.sub(pattern, "", cleaned).strip()
                if cleaned == before:
                    break
            return cleaned

        candidate = _clean(candidate)
        fallback = _clean(fallback)

        if fallback and not cls._is_garbled_text(fallback) and not cls._looks_like_noisy_title(fallback):
            chosen = fallback
        elif candidate and not cls._is_garbled_text(candidate) and not cls._looks_like_noisy_title(candidate):
            chosen = candidate
        elif fallback and not cls._is_garbled_text(fallback):
            chosen = fallback
        elif candidate and not cls._is_garbled_text(candidate):
            chosen = candidate
        else:
            options = [x for x in (fallback, candidate) if x]
            chosen = options[0] if options else ""

        if cls._is_garbled_text(chosen):
            reg = str(reg_number or "").strip()
            return f"Закупка {reg}" if reg else "Без названия"
        return chosen or "Без названия"

    @staticmethod
    def _eis_url(reg_number: Optional[str]) -> Optional[str]:
        reg = str(reg_number or "").strip()
        if not reg:
            return None
        return f"https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString={reg}"

    @staticmethod
    def _status_label(status: str) -> str:
        labels = {
            ZakupkaStatus.RAW: "Новая",
            ZakupkaStatus.AI_READY: "ИИ готов",
            ZakupkaStatus.AI_ERROR: "Ошибка ИИ",
            ZakupkaStatus.URL_READY: "Готова к подбору",
            ZakupkaStatus.STAGE4_DONE: "Есть варианты квартир",
            ZakupkaStatus.STAGE4_ERROR: "Нужна перепроверка",
            ZakupkaStatus.LISTINGS_FRESH: "Есть варианты квартир",
            ZakupkaStatus.LISTINGS_STALE: "Варианты требуют обновления",
        }
        return labels.get((status or "").strip(), "Неизвестно")

    @staticmethod
    def _public_status_label(status: str, listings_count: int) -> str:
        normalized = (status or "").strip()
        if normalized in (
            ZakupkaStatus.STAGE4_DONE,
            ZakupkaStatus.STAGE4_ERROR,
            ZakupkaStatus.LISTINGS_FRESH,
            ZakupkaStatus.LISTINGS_STALE,
        ):
            return "Есть варианты квартир" if (listings_count or 0) > 0 else "Нет вариантов квартир"
        return ViewService._status_label(normalized)

    @staticmethod
    def _external_label(source: Optional[str]) -> Optional[str]:
        normalized = (source or "").strip().lower()
        if normalized == "cian":
            return "Открыть на CIAN"
        if normalized == "domclick":
            return "Открыть на Домклик"
        return None

    @staticmethod
    def _format_rub(value: float) -> str:
        return f"{int(round(value)):,}".replace(",", " ") + " ₽"

    @staticmethod
    def _has_available_listings_label(listings_count: int) -> str:
        return "Да" if (listings_count or 0) > 0 else "Нет"

    @staticmethod
    def _end_reason_label(reason: Optional[str]) -> str:
        normalized = str(reason or "").strip().lower()
        if normalized == "manual_unreserve":
            return "Снято пользователем"
        if normalized == "expired":
            return "Истек срок брони"
        return "Завершено"

    @classmethod
    def calculate_margin_display(cls, initial_price: Optional[float], min_listing_price: Optional[float]) -> str:
        if min_listing_price is None:
            return "—"
        if initial_price is None or float(initial_price) <= 0:
            return "—"

        delta = float(initial_price) - float(min_listing_price)
        if delta <= 0:
            return "0.0% (0 ₽)"

        margin_pct = (delta / float(initial_price)) * 100.0
        return f"{margin_pct:.1f}% ({cls._format_rub(delta)})"

    @staticmethod
    def _bid_end_sort_key(value: Optional[str]) -> tuple[int, str]:
        raw = str(value or "").strip()
        if not raw:
            return 1, "9999-12-31"
        try:
            if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                dt = datetime.strptime(raw[:10], "%Y-%m-%d")
                return 0, dt.strftime("%Y-%m-%d")
            dt = datetime.strptime(raw[:10], "%d.%m.%Y")
            return 0, dt.strftime("%Y-%m-%d")
        except Exception:
            return 1, raw

    def _get_public_available_listings(self, reg_number: str, reserved_ids: Optional[set[int]] = None):
        listings = self.db.listings.get_for_zakupka(reg_number)
        if reserved_ids is None:
            if hasattr(self.db, "listing_reservations") and hasattr(self.db.listing_reservations, "get_active_reserved_listing_ids"):
                reserved_ids = self.db.listing_reservations.get_active_reserved_listing_ids(reg_number=reg_number)
            else:
                reserved_ids = set()
        return [item for item in listings if getattr(item, "id", None) not in reserved_ids]

    def get_public_zakupki_page(
        self,
        offset: int = 0,
        limit: int = 20,
        include_reserved: bool = False,
        current_user_email: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))
        statuses = (
            ZakupkaStatus.URL_READY,
            ZakupkaStatus.STAGE4_DONE,
            ZakupkaStatus.STAGE4_ERROR,
            ZakupkaStatus.LISTINGS_FRESH,
            ZakupkaStatus.LISTINGS_STALE,
        )

        all_rows: list[dict] = []
        if hasattr(self.db.zakupki, "get_public_list_page"):
            raw_items, _ = self.db.zakupki.get_public_list_page(list(statuses), offset=0, limit=1_000_000)
            all_rows = list(raw_items or [])
        else:
            items = self.db.zakupki.get_by_statuses(list(statuses))
            ordered = sorted(
                items,
                key=lambda x: (
                    x.prepared_at is None,
                    str(x.prepared_at or ""),
                    x.processed_at is None,
                    str(x.processed_at or ""),
                    x.update_date or "",
                ),
                reverse=True,
            )
            for x in ordered:
                all_rows.append(
                    {
                        "reg_number": x.reg_number,
                        "description": x.description,
                        "bid_end_date": x.bid_end_date,
                        "initial_price": x.initial_price,
                        "status": x.status,
                    }
                )

        reg_numbers_all = [z.get("reg_number") for z in all_rows if z.get("reg_number")]

        if hasattr(self.db, "listing_reservations") and hasattr(self.db.listing_reservations, "get_active_reserved_listing_ids_map"):
            reserved_map = self.db.listing_reservations.get_active_reserved_listing_ids_map(reg_numbers_all, expire=True)
        else:
            reserved_map = {reg: set() for reg in reg_numbers_all}

        if hasattr(self.db, "zakupka_reservations") and hasattr(self.db.zakupka_reservations, "get_active_reservations_map"):
            zakupka_reserved_map = self.db.zakupka_reservations.get_active_reservations_map(reg_numbers_all, expire=True)
        else:
            zakupka_reserved_map = {}

        if hasattr(self.db.ai_results, "get_by_reg_numbers_map"):
            ai_map = self.db.ai_results.get_by_reg_numbers_map(reg_numbers_all)
        else:
            ai_map = {}
            for reg in reg_numbers_all:
                ai = self.db.ai_results.get_by_id(reg)
                if ai:
                    ai_map[reg] = ai

        if hasattr(self.db.listings, "get_stats_for_zakupki"):
            listing_stats_map = self.db.listings.get_stats_for_zakupki(reg_numbers_all)
        else:
            listing_stats_map = {}
            for reg in reg_numbers_all:
                listings = self.db.listings.get_for_zakupka(reg)
                prices = [x.price_rub for x in listings if getattr(x, "price_rub", None) is not None]
                listing_stats_map[reg] = {"listings_count": len(listings), "min_price_rub": min(prices) if prices else None}

        favorites_map = {reg: False for reg in reg_numbers_all}
        if current_user_email and hasattr(self.db, "public_favorites") and hasattr(self.db.public_favorites, "get_favorite_reg_numbers_map"):
            favorites_map = self.db.public_favorites.get_favorite_reg_numbers_map(reg_numbers_all, current_user_email)

        filtered_rows = []
        for z in all_rows:
            reg = str(z.get("reg_number") or "").strip()
            if not reg:
                continue
            if (reg in zakupka_reserved_map) and not include_reserved:
                continue
            filtered_rows.append(z)

        # Sort: listings first, then by date
        def _sort_key(row):
            reg = str(row.get("reg_number") or "").strip()
            stats = listing_stats_map.get(reg, {})
            has_listings = 1 if (stats.get("listings_count") or 0) > 0 else 0
            return (
                has_listings,
                row.get("prepared_at") is not None,
                str(row.get("prepared_at") or ""),
                row.get("processed_at") is not None,
                str(row.get("processed_at") or ""),
                str(row.get("update_date") or ""),
            )

        filtered_rows.sort(key=_sort_key, reverse=True)

        total = len(filtered_rows)
        page_rows = filtered_rows[safe_offset : safe_offset + safe_limit]

        items: list[dict] = []
        for zakupka in page_rows:
            reg_number = str(zakupka.get("reg_number") or "").strip()
            if not reg_number:
                continue

            reserved_until = zakupka_reserved_map.get(reg_number)
            is_reserved = bool(reserved_until)

            ai_result = ai_map.get(reg_number)
            stats = listing_stats_map.get(reg_number, {"listings_count": 0, "min_price_rub": None})
            reserved_ids = reserved_map.get(reg_number, set())
            raw_count = int(stats.get("listings_count") or 0)
            listings_count = max(0, raw_count - len(reserved_ids))
            min_listing_price = float(stats.get("min_price_rub")) if stats.get("min_price_rub") is not None and listings_count > 0 else None

            title = self._pick_public_title(
                ai_result.zakupka_name if ai_result else None,
                zakupka.get("description"),
                reg_number=reg_number,
            )
            item = PublicZakupkaListItem(
                reg_number=reg_number,
                title=title,
                initial_price=zakupka.get("initial_price"),
                bid_end_date=zakupka.get("bid_end_date") or "",
                status=zakupka.get("status") or "",
                status_label=self._public_status_label(zakupka.get("status") or "", listings_count),
                has_available_listings_label=self._has_available_listings_label(listings_count),
                listings_count=listings_count,
                margin_display=self.calculate_margin_display(zakupka.get("initial_price"), min_listing_price),
                is_reserved=is_reserved,
                reserved_until=reserved_until,
                is_favorite=bool(favorites_map.get(reg_number)),
                eis_url=self._eis_url(reg_number),
            )
            items.append(asdict(item))

        return items, total

    def get_public_zakupka_detail(self, reg_number: str, current_user_email: Optional[str] = None) -> Optional[dict]:
        zakupka = self.db.zakupki.get_by_id(reg_number)
        if not zakupka:
            return None

        ai_result = self.db.ai_results.get_by_id(reg_number)
        listings = self._get_public_available_listings(reg_number)
        listings_count = len(listings)

        listing_views: list[PublicListingView] = []
        for listing in listings:
            listing_views.append(
                PublicListingView(
                    address=(listing.address or "").strip() or "Адрес не указан",
                    price_rub=listing.price_rub,
                    area_m2=listing.area_m2,
                    rooms=listing.rooms,
                    floor=listing.floor,
                    building_floors=listing.building_floors,
                    building_year=listing.building_year,
                    external_source=listing.external_source,
                    external_url=listing.external_url,
                    external_label=self._external_label(listing.external_source),
                )
            )

        prices = [item.price_rub for item in listings if item.price_rub is not None]
        min_listing_price = float(min(prices)) if prices else None

        if hasattr(self.db, "zakupka_reservations") and hasattr(self.db.zakupka_reservations, "get_active_reservations_map"):
            reserved_until = self.db.zakupka_reservations.get_active_reservations_map([zakupka.reg_number], expire=True).get(zakupka.reg_number)
        else:
            reserved_until = None

        is_favorite = False
        if current_user_email and hasattr(self.db, "public_favorites") and hasattr(self.db.public_favorites, "is_favorite"):
            is_favorite = bool(self.db.public_favorites.is_favorite(zakupka.reg_number, current_user_email))

        title = self._pick_public_title(
            ai_result.zakupka_name if ai_result else None,
            zakupka.description,
            reg_number=zakupka.reg_number,
        )
        detail = PublicZakupkaDetail(
            reg_number=zakupka.reg_number,
            title=title,
            initial_price=zakupka.initial_price,
            bid_end_date=zakupka.bid_end_date or "",
            status=zakupka.status,
            status_label=self._public_status_label(zakupka.status, listings_count),
            margin_display=self.calculate_margin_display(zakupka.initial_price, min_listing_price),
            is_reserved=bool(reserved_until),
            reserved_until=reserved_until,
            is_favorite=is_favorite,
            eis_url=self._eis_url(zakupka.reg_number),
            city=ai_result.city if ai_result else None,
            address=ai_result.address if ai_result else None,
            area_min_m2=ai_result.area_min_m2 if ai_result else None,
            area_max_m2=ai_result.area_max_m2 if ai_result else None,
            rooms=ai_result.rooms if ai_result else None,
            floor=ai_result.floor if ai_result else None,
            building_floors_min=ai_result.building_floors_min if ai_result else None,
            year_build_str=ai_result.year_build_str if ai_result else None,
            wear_percent=ai_result.wear_percent if ai_result else None,
            zakazchik=ai_result.zakazchik if ai_result else None,
            listings=listing_views,
        )
        return asdict(detail)

    def get_public_reservations_page(
        self,
        offset: int = 0,
        limit: int = 20,
        reserved_by: Optional[str] = None,
        tab: str = "active",
        status_filter: str = "all",
        sort_mode: str = "bid_end_asc",
    ) -> tuple[list[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))
        selected_tab = (tab or "active").strip().lower()
        selected_status_filter = (status_filter or "all").strip().lower()
        selected_sort = (sort_mode or "bid_end_asc").strip().lower()
        if selected_tab == "history" and selected_sort in {"", "default", "bid_end_asc"}:
            selected_sort = "history_desc"

        if selected_tab == "history" and hasattr(self.db.zakupka_reservations, "get_history_page"):
            rows, _ = self.db.zakupka_reservations.get_history_page(
                user_email=reserved_by or "",
                offset=0,
                limit=1_000_000,
            )
        else:
            selected_tab = "active"
            rows, _ = self.db.zakupka_reservations.get_active_page(
                offset=0,
                limit=1_000_000,
                reserved_by=reserved_by,
            )

        reg_numbers = [str(x.get("reg_number") or "").strip() for x in rows if x.get("reg_number")]
        if not reg_numbers:
            return [], 0

        zakupki_map = {z.reg_number: z for z in self.db.zakupki.get_by_reg_numbers(reg_numbers)}
        ai_map = self.db.ai_results.get_by_reg_numbers_map(reg_numbers) if hasattr(self.db.ai_results, "get_by_reg_numbers_map") else {}

        if hasattr(self.db.listings, "get_stats_for_zakupki"):
            listing_stats_map = self.db.listings.get_stats_for_zakupki(reg_numbers)
        else:
            listing_stats_map = {reg: {"listings_count": 0, "min_price_rub": None} for reg in reg_numbers}

        if hasattr(self.db, "listing_reservations") and hasattr(self.db.listing_reservations, "get_active_reserved_listing_ids_map"):
            reserved_ids_map = self.db.listing_reservations.get_active_reserved_listing_ids_map(reg_numbers, expire=True)
        else:
            reserved_ids_map = {reg: set() for reg in reg_numbers}

        items: list[dict] = []
        for row in rows:
            reg_number = str(row.get("reg_number") or "").strip()
            if not reg_number:
                continue
            zakupka = zakupki_map.get(reg_number)
            ai_result = ai_map.get(reg_number)
            stats = listing_stats_map.get(reg_number, {"listings_count": 0, "min_price_rub": None})
            reserved_ids = reserved_ids_map.get(reg_number, set())

            raw_count = int(stats.get("listings_count") or 0)
            listings_count = max(0, raw_count - len(reserved_ids))
            min_listing_price = float(stats.get("min_price_rub")) if stats.get("min_price_rub") is not None and listings_count > 0 else None

            title = self._pick_public_title(
                ai_result.zakupka_name if ai_result else None,
                zakupka.description if zakupka else None,
                reg_number=reg_number,
            )
            item_status = (
                "active"
                if selected_tab == "active"
                else ("expired" if str(row.get("end_reason") or "").strip().lower() == "expired" else "released")
            )
            items.append(
                {
                    "reg_number": reg_number,
                    "title": title,
                    "initial_price": zakupka.initial_price if zakupka else None,
                    "bid_end_date": zakupka.bid_end_date if zakupka else "",
                    "status_label": self._public_status_label(zakupka.status if zakupka else "", listings_count),
                    "margin_display": self.calculate_margin_display(zakupka.initial_price if zakupka else None, min_listing_price),
                    "reserved_until": row.get("expires_at"),
                    "is_active": selected_tab == "active",
                    "booking_from": row.get("reserved_at"),
                    "booking_to": row.get("updated_at") if selected_tab == "history" else row.get("expires_at"),
                    "booking_status": item_status,
                    "ended_at": row.get("updated_at") if selected_tab == "history" else None,
                    "end_reason": row.get("end_reason") if selected_tab == "history" else None,
                    "end_reason_label": self._end_reason_label(row.get("end_reason")) if selected_tab == "history" else None,
                }
            )

        if selected_status_filter in {"active", "released", "expired"}:
            items = [x for x in items if str(x.get("booking_status") or "").strip().lower() == selected_status_filter]

        if selected_tab == "history" and selected_sort in {"history_desc", "history_asc"}:
            reverse = selected_sort == "history_desc"
            items.sort(key=lambda x: str(x.get("ended_at") or x.get("booking_to") or ""), reverse=reverse)
        else:
            reverse = selected_sort == "bid_end_desc"
            items.sort(key=lambda x: self._bid_end_sort_key(x.get("bid_end_date")), reverse=reverse)

        total = len(items)
        page_items = items[safe_offset : safe_offset + safe_limit]
        return page_items, total

    def get_public_favorites_page(self, user_email: str, offset: int = 0, limit: int = 20) -> tuple[list[dict], int]:
        safe_offset = max(0, int(offset or 0))
        safe_limit = max(1, int(limit or 20))
        if not hasattr(self.db, "public_favorites") or not hasattr(self.db.public_favorites, "get_favorites_page"):
            return [], 0

        rows, total = self.db.public_favorites.get_favorites_page(user_email=user_email, offset=safe_offset, limit=safe_limit)
        reg_numbers = [str(x.get("reg_number") or "").strip() for x in rows if x.get("reg_number")]
        if not reg_numbers:
            return [], total

        zakupki_map = {z.reg_number: z for z in self.db.zakupki.get_by_reg_numbers(reg_numbers)}
        ai_map = self.db.ai_results.get_by_reg_numbers_map(reg_numbers) if hasattr(self.db.ai_results, "get_by_reg_numbers_map") else {}
        listing_stats_map = self.db.listings.get_stats_for_zakupki(reg_numbers) if hasattr(self.db.listings, "get_stats_for_zakupki") else {reg: {"listings_count": 0, "min_price_rub": None} for reg in reg_numbers}
        reserved_map = self.db.zakupka_reservations.get_active_reservations_map(reg_numbers, expire=True) if hasattr(self.db, "zakupka_reservations") else {}

        items = []
        for row in rows:
            reg_number = str(row.get("reg_number") or "").strip()
            if not reg_number:
                continue
            zakupka = zakupki_map.get(reg_number)
            ai_result = ai_map.get(reg_number)
            stats = listing_stats_map.get(reg_number, {"listings_count": 0, "min_price_rub": None})
            listings_count = int(stats.get("listings_count") or 0)
            min_listing_price = float(stats.get("min_price_rub")) if stats.get("min_price_rub") is not None else None
            title = self._pick_public_title(
                ai_result.zakupka_name if ai_result else None,
                zakupka.description if zakupka else None,
                reg_number=reg_number,
            )
            items.append(
                {
                    "reg_number": reg_number,
                    "title": title,
                    "initial_price": zakupka.initial_price if zakupka else None,
                    "bid_end_date": zakupka.bid_end_date if zakupka else "",
                    "status_label": self._public_status_label(zakupka.status if zakupka else "", listings_count),
                    "margin_display": self.calculate_margin_display(zakupka.initial_price if zakupka else None, min_listing_price),
                    "is_reserved": reg_number in reserved_map,
                    "reserved_until": reserved_map.get(reg_number),
                    "is_favorite": True,
                    "favorited_at": row.get("created_at"),
                }
            )

        return items, total

    def get_zakupka_stage_view(self, user_id: int, stage: int, limit: int = 100) -> List[ZakupkaStageView]:
        """Build stage table rows for admin workflow pages."""
        result = []

        try:
            if stage == 1:
                all_zakupki = self.db.zakupki.get_all()
                zakupki = sorted(all_zakupki, key=lambda x: str(x.processed_at) if x.processed_at else "", reverse=True)
                zakupki = zakupki[:limit]
            elif stage == 2:
                zakupki = self.db.get_stage2_pending_items(overwrite=False, limit=None)
                self.logger.info("Stage2 view selection: selected=%s", len(zakupki))
            else:
                prev_stage = stage - 1
                zakupki = self.db.get_zakupki_for_stage(user_id, prev_stage)

            for z in zakupki:
                decision = self.db.decisions.get_last_decision(user_id, z.reg_number, stage)
                ai_result = self.db.ai_results.get_by_id(z.reg_number)
                listings = self.db.listings.get_for_zakupka(z.reg_number)

                listings_count = len(listings) if listings else 0
                listings_min_price = None
                listings_max_price = None

                if listings_count > 0:
                    prices = [item.price_rub for item in listings if item.price_rub is not None]
                    if prices:
                        listings_min_price = min(prices)
                        listings_max_price = max(prices)

                view = ZakupkaStageView(
                    reg_number=z.reg_number,
                    description=z.description or "",
                    update_date=z.update_date or "",
                    bid_end_date=z.bid_end_date or "",
                    initial_price=z.initial_price,
                    stage=stage,
                    processed_at=z.processed_at.isoformat() if z.processed_at else None,
                    my_decision=decision.decision if decision else None,
                    my_decision_comment=decision.comment if decision else None,
                    has_ai_result=ai_result is not None,
                    ai_zakupka_name=ai_result.zakupka_name if ai_result else None,
                    ai_address=ai_result.address if ai_result else None,
                    ai_city=ai_result.city if ai_result else None,
                    ai_area_min=ai_result.area_min_m2 if ai_result else None,
                    ai_area_max=ai_result.area_max_m2 if ai_result else None,
                    ai_rooms=ai_result.rooms if ai_result else None,
                    ai_rooms_parsed=ai_result.rooms_parsed if ai_result else None,
                    ai_floor=ai_result.floor if ai_result else None,
                    ai_building_floors_min=ai_result.building_floors_min if ai_result else None,
                    ai_year_build=ai_result.year_build_str if ai_result else None,
                    ai_wear_percent=ai_result.wear_percent if ai_result else None,
                    ai_zakazchik=ai_result.zakazchik if ai_result else None,
                    listings_count=listings_count,
                    listings_min_price=listings_min_price,
                    listings_max_price=listings_max_price,
                    combined_text=z.combined_text or "",
                )
                result.append(view)

        except Exception as e:
            self.logger.error("Failed to build view models: %s", e)

        return result
