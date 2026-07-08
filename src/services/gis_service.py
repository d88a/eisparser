"""
Сервис для генерации URL 2ГИС.
"""

import csv
from typing import Optional, Tuple, List

from config.settings import settings
from utils.logger import get_logger


class GISService:
    """Сервис для работы с 2ГИС и генерации URL поиска недвижимости."""

    STAGE3_URL_PREFIX = "https://2gis.ru/realty/sale/filters"
    LEGACY_STAGE3_SEARCH_PREFIX = "https://2gis.ru/search/"
    # 2GIS filter id for "Квартира" (exclude rooms/shares/houses in public filters)
    APARTMENT_TYPE_2GIS_ID = "1067258717690367200"

    def __init__(self, csv_path: str = None):
        self.csv_path = csv_path or settings.coordinates_csv_path
        self.logger = get_logger("GISService")
        self._coordinates_cache = {}

    def find_coordinates(self, city_name: str) -> Optional[Tuple[float, float]]:
        """Возвращает координаты города (lat, lon) из CSV."""
        city_lower = self._normalize_city(city_name)
        if not city_lower:
            return None

        if city_lower in self._coordinates_cache:
            return self._coordinates_cache[city_lower]

        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["name"].strip().lower() == city_lower:
                        coords = (float(row["lat"]), float(row["lon"]))
                        self._coordinates_cache[city_lower] = coords
                        self.logger.debug(
                            f"Найдены координаты для {city_name} (norm={city_lower}): {coords}"
                        )
                        return coords
        except FileNotFoundError:
            self.logger.error(f"Файл координат не найден: {self.csv_path}")
        except Exception as e:
            self.logger.error(f"Ошибка чтения CSV: {e}")

        return None

    def _normalize_city(self, city_name: str) -> str:
        if not city_name:
            return ""

        name = city_name.strip().lower()
        for prefix in ("г.", "г ", "город "):
            if name.startswith(prefix):
                name = name[len(prefix):].strip()
                break
        return name

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
        apartment_only: bool = True,
        on_map: bool = True,
        zoom: float = 14.67,
    ) -> Optional[str]:
        """Строит URL поиска в 2ГИС по координатам и фильтрам."""
        try:
            from gis.filters import build_komnat_fragment, build_range_fragment, join_fragments
        except ImportError:
            self.logger.error("Не удалось импортировать gis.filters")
            return None

        fragments = []

        if sort:
            fragments.append(f"sort={sort}")

        if apartment_only:
            fragments.append(f"tip_pomeshcheniya={self.APARTMENT_TYPE_2GIS_ID}")

        area_frag = build_range_fragment("obshchaya_ploshchad", area_min, area_max)
        if area_frag:
            fragments.append(area_frag)

        if rooms_counts:
            komnat_frag = build_komnat_fragment(rooms_counts)
            if komnat_frag:
                fragments.append(komnat_frag)

        floor_frag = build_range_fragment("etazh", floor_min, None)
        if floor_frag:
            fragments.append(floor_frag)

        price_frag = build_range_fragment("price", None, price_max)
        if price_frag:
            fragments.append(price_frag)

        filters_str = join_fragments(fragments) if fragments else ""
        base = "https://2gis.ru/realty/sale/filters/on_map" if on_map else self.STAGE3_URL_PREFIX

        if filters_str:
            url = f"{base}%3B{filters_str}"
        else:
            url = base

        url += f"?m={lon}%2C{lat}%2F{zoom}"
        self.logger.debug(f"Сгенерирован URL: {url[:120]}...")
        return url

    def build_url_for_city(self, city: str, **kwargs) -> Optional[str]:
        """Строит URL по названию города. Без fallback в /search/."""
        coords = self.find_coordinates(city)
        if not coords:
            self.logger.warning(f"Город не найден в CSV координат: {city}")
            return None

        lat, lon = coords
        return self.build_url(lon, lat, **kwargs)

    def is_stage3_url(self, url: Optional[str]) -> bool:
        """Проверяет, что ссылка соответствует формату Stage 3.

        Поддерживает:
        - текущий формат Stage 3: /realty/sale/filters...
        - legacy-формат из ранних версий: /search/...
        """
        if not url:
            return False
        value = str(url)
        return value.startswith(self.STAGE3_URL_PREFIX) or value.startswith(self.LEGACY_STAGE3_SEARCH_PREFIX)
