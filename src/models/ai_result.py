"""
Модель результата ИИ-анализа.
"""
from dataclasses import dataclass, asdict
from typing import Optional, List


@dataclass
class AIResult:
    """Результат ИИ-анализа закупки."""
    
    reg_number: str                         # Связь с закупкой
    zakupka_name: Optional[str] = None      # Название
    address: Optional[str] = None           # Адрес
    city: Optional[str] = None              # Город
    area_min_m2: Optional[float] = None     # Мин. площадь
    area_max_m2: Optional[float] = None     # Макс. площадь
    rooms: Optional[str] = None             # Комнаты (текст)
    rooms_parsed: Optional[str] = None      # Комнаты (JSON: [1,2,3])
    floor: Optional[str] = None             # Этаж (текст)
    building_floors_min: Optional[str] = None  # Мин. этажность
    year_build_str: Optional[str] = None    # Год постройки (текст)
    wear_percent: Optional[float] = None    # Износ %
    zakazchik: Optional[str] = None         # Заказчик
    
    def to_dict(self) -> dict:
        """Преобразует в словарь."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AIResult':
        """Создаёт объект из словаря."""
        return cls(
            reg_number=data.get('reg_number', ''),
            zakupka_name=data.get('zakupka_name'),
            address=data.get('address'),
            city=data.get('city'),
            area_min_m2=data.get('area_min_m2'),
            area_max_m2=data.get('area_max_m2'),
            rooms=data.get('rooms'),
            rooms_parsed=data.get('rooms_parsed'),
            floor=data.get('floor'),
            building_floors_min=data.get('building_floors_min'),
            year_build_str=data.get('year_build_str'),
            wear_percent=data.get('wear_percent'),
            zakazchik=data.get('zakazchik')
        )
    
    def get_rooms_list(self) -> List[int]:
        """Парсит rooms_parsed в список чисел."""
        if not self.rooms_parsed:
            return []
        try:
            # rooms_parsed может быть: "1", "2", "1,2,3", "1-3", "[1,2,3]" 
            import json
            import re
            
            s = str(self.rooms_parsed).strip()
            
            # Попробуем JSON
            try:
                parsed = json.loads(s)
                if isinstance(parsed, int):
                    return [parsed]
                elif isinstance(parsed, list):
                    return [int(x) for x in parsed]
            except:
                pass
            
            # Диапазон: "1-3" -> [1, 2, 3]
            range_match = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', s)
            if range_match:
                start, end = int(range_match.group(1)), int(range_match.group(2))
                return list(range(start, end + 1))
            
            # Список через запятую: "1,2,3"
            if ',' in s:
                return [int(x.strip()) for x in s.split(',') if x.strip().isdigit()]
            
            # Просто число: "1", "2"
            if s.isdigit():
                return [int(s)]
            
            return []
        except:
            return []
