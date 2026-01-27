"""
Сервис для генерации URL 2ГИС.
"""
import csv
from typing import Optional, Tuple, List
from utils.logger import get_logger
from config.settings import settings


class GISService:
    """
    Сервис для работы с 2ГИС.
    Генерирует URL для поиска недвижимости.
    """
    
    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or settings.coordinates_csv_path
        self.logger = get_logger("GISService")
        self._coordinates_cache = {}
    
    def find_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """
        Находит координаты города.
        
        Args:
            city_name: Название города
        
        Returns:
            Кортеж (lat, lon) или None
        """
        # Проверяем кэш
        city_lower = city_name.strip().lower()
        if city_lower in self._coordinates_cache:
            return self._coordinates_cache[city_lower]
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['name'].strip().lower() == city_lower:
                        coords = (float(row['lat']), float(row['lon']))
                        self._coordinates_cache[city_lower] = coords
                        self.logger.debug(f"Найдены координаты для {city_name}: {coords}")
                        return coords
        except FileNotFoundError:
            self.logger.error(f"Файл координат не найден: {self.csv_path}")
        except Exception as e:
            self.logger.error(f"Ошибка чтения CSV: {e}")
        
        return None
    
    def build_url(
        self,
        lon: float,
        lat: float,
        *,
        area_min: float = None,
        area_max: float = None,
        rooms_counts: List[int] = None,
        floor_min: int = None,
        price_max: float = None,
        sort: str = "price_asc",
        on_map: bool = True,
        zoom: float = 14.67
    ) -> str:
        """
        Строит URL для поиска недвижимости в 2ГИС.
        
        Args:
            lon, lat: Координаты
            area_min, area_max: Диапазон площади
            rooms_counts: Список количества комнат
            floor_min: Минимальный этаж
            price_max: Максимальная цена
            sort: Сортировка
            on_map: Показывать на карте
            zoom: Масштаб карты
        
        Returns:
            URL для 2ГИС
        """
        # Импортируем функции из существующего модуля gis
        try:
            from gis.filters import (
                build_range_fragment,
                build_komnat_fragment,
                join_fragments
            )
        except ImportError:
            self.logger.error("Не удалось импортировать gis.filters")
            return f"https://2gis.ru/search/{lat},{lon}"
        
        fragments = []
        
        # Сортировка
        if sort:
            fragments.append(f"sort={sort}")
        
        # Площадь
        area_frag = build_range_fragment("obshchaya_ploshchad", area_min, area_max)
        if area_frag:
            fragments.append(area_frag)
        
        # Комнаты
        if rooms_counts:
            komnat_frag = build_komnat_fragment(rooms_counts)
            if komnat_frag:
                fragments.append(komnat_frag)
        
        # Этаж
        floor_frag = build_range_fragment("etazh", floor_min, None)
        if floor_frag:
            fragments.append(floor_frag)
        
        # Цена
        price_frag = build_range_fragment("price", None, price_max)
        if price_frag:
            fragments.append(price_frag)
        
        # Собираем URL
        filters_str = join_fragments(fragments) if fragments else ""
        
        if on_map:
            base = f"https://2gis.ru/realty/sale/filters/on_map"
        else:
            base = f"https://2gis.ru/realty/sale/filters"
        
        if filters_str:
            url = f"{base}%3B{filters_str}"
        else:
            url = base
        
        # Добавляем координаты
        url += f"?m={lon}%2C{lat}%2F{zoom}"
        
        self.logger.debug(f"Сгенерирован URL: {url[:80]}...")
        return url
    
    def build_url_for_city(
        self,
        city: str,
        **kwargs
    ) -> Optional[str]:
        """
        Строит URL по названию города.
        
        Args:
            city: Название города
            **kwargs: Параметры для build_url
        
        Returns:
            URL или None если город не найден
        """
        coords = self.find_coordinates(city)
        if not coords:
            self.logger.warning(f"Город не найден: {city}")
            return None
        
        lat, lon = coords
        return self.build_url(lon, lat, **kwargs)
