# realty_scraper/parsers.py
"""
Парсеры для извлечения данных из текста объявлений 2ГИС.
"""
import re
from typing import Optional, Tuple


def parse_price(text: str) -> Optional[int]:
    """
    Парсит цену из текста.
    
    Примеры:
        "3 543 896 ₽" -> 3543896
        "3543896" -> 3543896
        "3,5 млн ₽" -> 3500000
        "3.5 млн" -> 3500000
    """
    if not text:
        return None
    
    text = str(text).strip()
    
    # Сначала ищем строку с символом рубля — это наиболее надёжный признак цены
    price_lines = []
    for line in text.split('\n'):
        if '₽' in line or 'руб' in line.lower():
            price_lines.append(line)
    
    # Если нашли строки с ценой, парсим первую
    if price_lines:
        price_text = price_lines[0]
    else:
        # Если нет строки с ₽, возвращаем None
        return None
    
    price_text = price_text.lower().replace('₽', '').replace('\xa0', ' ').strip()
    
    # Проверяем на "млн"
    mln_match = re.search(r'([\d,\.]+)\s*млн', price_text)
    if mln_match:
        value_str = mln_match.group(1).replace(',', '.')
        try:
            return int(float(value_str) * 1_000_000)
        except ValueError:
            pass
    
    # Ищем число формата "X XXX XXX" (цена с пробелами)
    # Удаляем все кроме цифр и пробелов, потом убираем пробелы
    clean_text = re.sub(r'[^\d\s]', '', price_text)
    clean_text = clean_text.replace(' ', '').strip()
    
    if clean_text and clean_text.isdigit():
        value = int(clean_text)
        # Проверяем что это похоже на цену (от 100 000 до 1 000 000 000)
        if 100_000 <= value <= 1_000_000_000:
            return value
    
    return None


def parse_area(text: str) -> Optional[float]:
    """
    Парсит площадь из текста.
    
    Примеры:
        "30 м²" -> 30.0
        "30.5 м²" -> 30.5
        "30,5 кв.м" -> 30.5
        "площадь 45" -> 45.0
    """
    if not text:
        return None
    
    text = str(text).strip().lower()
    
    # Ищем число перед "м²" или "кв"
    patterns = [
        r'([\d,\.]+)\s*м[²2]',      # 30 м² или 30 м2
        r'([\d,\.]+)\s*кв\.?\s*м',  # 30 кв.м или 30 кв м
        r'([\d,\.]+)\s*кв\.?',      # 30 кв.
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value_str = match.group(1).replace(',', '.')
            try:
                return float(value_str)
            except ValueError:
                pass
    
    # Попытка извлечь просто число
    numbers = re.findall(r'([\d,\.]+)', text)
    if numbers:
        try:
            return float(numbers[0].replace(',', '.'))
        except ValueError:
            pass
    
    return None


def parse_floor(text: str) -> Optional[Tuple[int, int]]:
    """
    Парсит этаж из текста.
    
    Примеры:
        "1/9" -> (1, 9)
        "этаж 1 из 9" -> (1, 9)
        "1 этаж, 9 этажей" -> (1, 9)
        "5" -> (5, None)
    
    Returns:
        Tuple[floor, building_floors] или None
    """
    if not text:
        return None
    
    text = str(text).strip().lower()
    
    # Паттерн "X/Y" или "X из Y"
    patterns = [
        r'(\d+)\s*/\s*(\d+)',           # 1/9
        r'(\d+)\s*из\s*(\d+)',          # 1 из 9
        r'этаж\s*(\d+)\s*из\s*(\d+)',   # этаж 1 из 9
        r'(\d+)\s*этаж.*?(\d+)\s*этаж', # 1 этаж, 9 этажей
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                floor = int(match.group(1))
                building = int(match.group(2))
                return (floor, building)
            except (ValueError, IndexError):
                pass
    
    # Только этаж без этажности здания
    floor_match = re.search(r'(\d+)\s*этаж', text)
    if floor_match:
        try:
            return (int(floor_match.group(1)), None)
        except ValueError:
            pass
    
    # Просто число
    if text.isdigit():
        return (int(text), None)
    
    return None


def parse_rooms(text: str) -> Optional[int]:
    """
    Парсит количество комнат из текста.
    
    Примеры:
        "1-к" -> 1
        "1-комн" -> 1
        "2-комнатная" -> 2
        "студия" -> 0
        "3 комн" -> 3
    """
    if not text:
        return None
    
    text = str(text).strip().lower()
    
    # Студия
    if 'студ' in text:
        return 0
    
    # Паттерны
    patterns = [
        r'(\d+)\s*-?\s*к(?:омн|\.)',  # 1-к, 1-комн, 1 комн
        r'(\d+)\s*комн',               # 1 комнат
        r'(\d+)\s*-?\s*к$',            # 1-к, 1к
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
    
    # Просто число в начале
    if text and text[0].isdigit():
        try:
            return int(text[0])
        except ValueError:
            pass
    
    return None


def parse_building_year(text: str) -> Optional[int]:
    """
    Парсит год постройки из текста.
    
    Примеры:
        "2012" -> 2012
        "год постройки: 2015" -> 2015
        "построен в 2010" -> 2010
    """
    if not text:
        return None
    
    text = str(text).strip()
    
    # Ищем 4-значный год (1900-2099)
    year_match = re.search(r'(19\d{2}|20\d{2})', text)
    if year_match:
        try:
            return int(year_match.group(1))
        except ValueError:
            pass
    
    return None


def classify_external_source(url: str) -> str:
    """
    Классифицирует внешний источник по URL.
    
    Returns:
        "domclick" | "cian" | "avito" | "other"
    """
    if not url:
        return "unknown"
    
    url = url.lower()
    
    if 'domclick' in url or 'domclick.ru' in url:
        return "domclick"
    elif 'cian' in url or 'cian.ru' in url:
        return "cian"
    elif 'avito' in url or 'avito.ru' in url:
        return "avito"
    else:
        return "other"
