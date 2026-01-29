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
    
    # Новые поля для системы статусов
    status: str = "raw"                     # Статус: raw, ai_processing, ai_ready, url_ready, user_selected, listings_fresh, listings_stale
    prepared_by_user_id: Optional[int] = None  # ID админа, который подготовил закупку
    prepared_at: Optional[datetime] = None  # Время завершения подготовки (Stage 3)
    
    def to_dict(self) -> dict:
        """Преобразует в словарь для сохранения в БД."""
        data = asdict(self)
        if self.processed_at:
            data['processed_at'] = self.processed_at.isoformat()
        if self.prepared_at:
            data['prepared_at'] = self.prepared_at.isoformat()
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
        
        prepared_at = data.get('prepared_at')
        if prepared_at and isinstance(prepared_at, str):
            try:
                prepared_at = datetime.fromisoformat(prepared_at)
            except:
                prepared_at = None
        
        return cls(
            reg_number=data.get('reg_number', ''),
            description=data.get('description', ''),
            update_date=data.get('update_date', ''),
            bid_end_date=data.get('bid_end_date', ''),
            initial_price=data.get('initial_price'),
            link=data.get('link', ''),
            combined_text=data.get('combined_text', ''),
            two_gis_url=data.get('two_gis_url'),
            processed_at=processed_at,
            status=data.get('status', 'raw'),
            prepared_by_user_id=data.get('prepared_by_user_id'),
            prepared_at=prepared_at
        )
