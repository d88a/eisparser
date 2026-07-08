"""Модель закупки с ЕИС."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Zakupka:
    """Закупка недвижимости с сайта ЕИС."""

    reg_number: str
    description: str = ""
    update_date: str = ""
    bid_end_date: str = ""
    initial_price: Optional[float] = None
    link: str = ""
    combined_text: str = ""
    two_gis_url: Optional[str] = None
    processed_at: Optional[datetime] = None

    # Status flow: raw -> ai_ready/ai_error -> url_ready -> stage4_done/stage4_error
    status: str = "raw"
    prepared_by_user_id: Optional[int] = None
    prepared_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Преобразует в словарь для сохранения в БД."""
        data = asdict(self)
        if self.processed_at:
            data["processed_at"] = self.processed_at.isoformat()
        if self.prepared_at:
            data["prepared_at"] = self.prepared_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Zakupka":
        """Создаёт объект из словаря (из БД)."""
        processed_at = data.get("processed_at")
        if processed_at and isinstance(processed_at, str):
            try:
                processed_at = datetime.fromisoformat(processed_at)
            except Exception:
                processed_at = None

        prepared_at = data.get("prepared_at")
        if prepared_at and isinstance(prepared_at, str):
            try:
                prepared_at = datetime.fromisoformat(prepared_at)
            except Exception:
                prepared_at = None

        return cls(
            reg_number=data.get("reg_number", ""),
            description=data.get("description", ""),
            update_date=data.get("update_date", ""),
            bid_end_date=data.get("bid_end_date", ""),
            initial_price=data.get("initial_price"),
            link=data.get("link", ""),
            combined_text=data.get("combined_text", ""),
            two_gis_url=data.get("two_gis_url"),
            processed_at=processed_at,
            status=data.get("status", "raw"),
            prepared_by_user_id=data.get("prepared_by_user_id"),
            prepared_at=prepared_at,
        )
