"""
View-модели для отображения данных пайплайна.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ZakupkaStageView:
    """
    Модель для отображения закупки на этапе.
    Агрегирует данные из Zakupka, Decision, AIResult и Listings.
    Read-only view model.
    """
    # Основные данные закупки
    reg_number: str
    description: str
    update_date: str
    bid_end_date: str  # Дата окончания подачи заявок
    initial_price: Optional[float]  # Начальная цена
    stage: int

    # Решение пользователя
    my_decision: Optional[str] = None
    my_decision_comment: Optional[str] = None
    
    # Результаты ИИ - ВСЕ ПОЛЯ из AIResult
    has_ai_result: bool = False
    ai_zakupka_name: Optional[str] = None
    ai_address: Optional[str] = None
    ai_city: Optional[str] = None
    ai_area_min: Optional[float] = None
    ai_area_max: Optional[float] = None
    ai_rooms: Optional[str] = None
    ai_rooms_parsed: Optional[str] = None
    ai_floor: Optional[str] = None
    ai_building_floors_min: Optional[str] = None
    ai_year_build: Optional[str] = None
    ai_wear_percent: Optional[float] = None
    ai_zakazchik: Optional[str] = None
    
    # Агрегаты по объявлениям
    listings_count: int = 0
    listings_min_price: Optional[int] = None
    listings_max_price: Optional[int] = None
    
    # Stage 2 specific
    combined_text: Optional[str] = None
    processed_at: Optional[str] = None


@dataclass
class PublicZakupkaListItem:
    """Read-only item for the public purchases list."""

    reg_number: str
    title: str
    initial_price: Optional[float] = None
    bid_end_date: str = ""
    status: str = ""
    status_label: str = ""
    has_available_listings_label: str = "Нет"
    listings_count: int = 0
    margin_display: str = "—"
    is_reserved: bool = False
    reserved_until: Optional[str] = None
    is_favorite: bool = False
    eis_url: Optional[str] = None


@dataclass
class PublicListingView:
    """Read-only public listing card data."""

    address: str
    price_rub: Optional[int] = None
    area_m2: Optional[float] = None
    rooms: Optional[int] = None
    floor: Optional[int] = None
    building_floors: Optional[int] = None
    building_year: Optional[int] = None
    external_source: Optional[str] = None
    external_url: Optional[str] = None
    external_label: Optional[str] = None


@dataclass
class PublicZakupkaDetail:
    """Read-only public purchase detail page payload."""

    reg_number: str
    title: str
    initial_price: Optional[float]
    bid_end_date: str
    status: str
    status_label: str
    margin_display: str = "—"
    is_reserved: bool = False
    reserved_until: Optional[str] = None
    is_favorite: bool = False
    eis_url: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    area_min_m2: Optional[float] = None
    area_max_m2: Optional[float] = None
    rooms: Optional[str] = None
    floor: Optional[str] = None
    building_floors_min: Optional[str] = None
    year_build_str: Optional[str] = None
    wear_percent: Optional[float] = None
    zakazchik: Optional[str] = None
    listings: Optional[list[PublicListingView]] = None
