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
    my_decision: Optional[str]
    my_decision_comment: Optional[str]
    
    # Результаты ИИ - ВСЕ ПОЛЯ из AIResult
    has_ai_result: bool
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
