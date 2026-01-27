# realty_scraper/models.py
"""
Модели данных для объявлений недвижимости.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Listing:
    """Объявление о продаже недвижимости из 2ГИС."""
    
    rank: int                                   # Позиция в выдаче
    price_rub: int                              # Цена в рублях
    address: str                                # Адрес
    rooms: Optional[int] = None                 # Количество комнат (0 = студия)
    area_m2: Optional[float] = None             # Площадь в м²
    floor: Optional[int] = None                 # Этаж квартиры
    building_floors: Optional[int] = None       # Этажей в здании
    building_year: Optional[int] = None         # Год постройки
    two_gis_url: Optional[str] = None           # Ссылка на объявление в 2ГИС
    external_source: Optional[str] = None       # domclick|cian|other|null
    external_url: Optional[str] = None          # Внешняя ссылка
    
    def to_dict(self) -> dict:
        """Преобразует объект в словарь."""
        return asdict(self)


@dataclass
class ListingResult:
    """Результат сбора объявлений по одной ссылке."""
    
    source: str = "2gis"
    query_url: str = ""
    sort: str = "price_asc"
    fetched_at: str = ""
    top_n: int = 0
    actual_n: int = 0
    items: list = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.items is None:
            self.items = []
        if not self.fetched_at:
            self.fetched_at = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """Преобразует объект в словарь."""
        return {
            "source": self.source,
            "query_url": self.query_url,
            "sort": self.sort,
            "fetched_at": self.fetched_at,
            "top_n": self.top_n,
            "actual_n": self.actual_n,
            "items": [item.to_dict() if hasattr(item, 'to_dict') else item for item in self.items],
            "error": self.error
        }
