"""
Модель закупки с ЕИС.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from datetime import datetime


@dataclass
class Zakupka:
    """Закупка недвижимости с сайта ЕИС."""
    
    reg_number: str                         # Регистрационный номер
    description: str = ""                   # Описание закупки
    update_date: str = ""                   # Дата обновления
    bid_end_date: str = ""                  # Дата окончания подачи заявок
    initial_price: Optional[float] = None   # Начальная цена
    link: str = ""                          # Ссылка на ЕИС
    combined_text: str = ""                 # Полный текст
    two_gis_url: Optional[str] = None       # Сгенерированная ссылка 2ГИС
    processed_at: Optional[datetime] = None # Время обработки
    
    def to_dict(self) -> dict:
        """Преобразует в словарь для сохранения в БД."""
        data = asdict(self)
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Zakupka':
        """Создаёт объект из словаря (из БД)."""
        processed_at = data.get('processed_at')
        if processed_at and isinstance(processed_at, str):
            try:
                processed_at = datetime.fromisoformat(processed_at)
            except:
                processed_at = None
        
        return cls(
            reg_number=data.get('reg_number', ''),
            description=data.get('description', ''),
            update_date=data.get('update_date', ''),
            bid_end_date=data.get('bid_end_date', ''),
            initial_price=data.get('initial_price'),
            link=data.get('link', ''),
            combined_text=data.get('combined_text', ''),
            two_gis_url=data.get('two_gis_url'),
            processed_at=processed_at
        )
