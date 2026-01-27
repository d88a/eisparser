"""
Пакет для работы с 2ГИС.

Публичное API:
- generator.find_coordinates_by_city
- generator.build_2gis_realty_url
- parser.parse_2gis_listings
"""

from .generator import find_coordinates_by_city, build_2gis_realty_url
from .parser import parse_2gis_listings
