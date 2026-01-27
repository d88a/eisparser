# project_real/project_root/gis/generator.py
"""
Генерация ссылки поиска 2ГИС по городу и параметрам.

Публичное API:
- find_coordinates_by_city(city_name: str) -> tuple[float, float] | None
- build_2gis_realty_url(...) -> str
"""
import csv
import os
from .filters import (
    normalize_float,
    normalize_int,
    normalize_rooms_counts,
    build_range_fragment,
    build_komnat_fragment,
    join_fragments,
)


def find_coordinates_by_city(city_name: str) -> tuple[float, float] | None:
    """
    Поиск координат по названию города в CSV файле.
    Возвращает (широта, долгота) или None.
    """
    # Очистка от префиксов населённых пунктов
    prefixes = ["г.", "г ", "п.", "п ", "с.", "с ", "д.", "д ",
               "пос.", "пос ", "село ", "город ", "деревня "]
    clean_name = city_name.strip()
    for prefix in prefixes:
        if clean_name.lower().startswith(prefix.lower()):
            clean_name = clean_name[len(prefix):].strip()
            break
    
    csv_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'map', 'ru_localities_geoapify.csv'
    )
    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['name'].strip().lower() == clean_name.lower():
                    lat = float(row['lat'])
                    lon = float(row['lon'])
                    return (lat, lon)
    except FileNotFoundError:
        print(f"Файл {csv_path} не найден")
        return None
    except Exception as e:
        print(f"Ошибка при чтении CSV файла: {e}")
        return None
    return None


def build_2gis_realty_url(
    lon: float,
    lat: float,
    *,
    area_min: float | None = None,
    area_max: float | None = None,
    rooms_counts: list[int] | None = None,
    floor_min: int | None = None,
    price_max: float | None = None,
    sort: str = "price_asc",
    on_map: bool = True,
    zoom: float = 14.67,
) -> str:
    """Build a 2GIS real-estate URL using normalized parameters.

    The function follows the specification from the implementation plan:
    - Normalizes numeric inputs.
    - Constructs filter fragments in the required order:
      1. komnat (rooms)
      2. on_map
      3. sort
      4. obshchaya_ploshchad (area)
      5. etazh (floor)
      6. price
    - Joins fragments with ';' (URL-encoded as %3B).
    - Appends coordinate part `?m={lon},{lat}/{zoom}`.

    If no filters are provided, returns a simple URL with just coordinates.
    """
    # Normalize values
    area_min_f = normalize_float(area_min)
    area_max_f = normalize_float(area_max)
    floor_min_i = normalize_int(floor_min)
    price_max_f = normalize_float(price_max)
    rooms = normalize_rooms_counts(rooms_counts)

    fragments: list[str] = []

    # 1. Rooms fragment
    if rooms:
        komnat = build_komnat_fragment(rooms)
        if komnat:
            fragments.append(komnat)

    # 2. on_map flag
    if on_map:
        fragments.append("on_map")

    # 3. Sort
    if sort:
        fragments.append(f"sort={sort}")

    # 4. Area fragment
    area_frag = build_range_fragment("obshchaya_ploshchad", area_min_f, area_max_f)
    if area_frag:
        fragments.append(area_frag)

    # 5. Floor fragment (только минимальный этаж)
    if floor_min_i is not None:
        fragments.append(f"etazh={floor_min_i},")

    # 6. Price fragment (only max supported)
    if price_max_f is not None:
        fragments.append(f"price=,{int(price_max_f)}")

    # Build URL
    if fragments:
        filter_path = join_fragments(fragments)
        # Encode semicolons and commas for URL
        filter_path_encoded = filter_path.replace(";", "%3B").replace(",", "%2C").replace("=", "%3D")
        base_url = f"https://2gis.ru/realty/sale/filters/{filter_path_encoded}?m={lon}%2C{lat}%2F{zoom}"
    else:
        # No filters - simple URL with coordinates only
        base_url = f"https://2gis.ru/?m={lon}%2C{lat}%2F{zoom}"

    return base_url
