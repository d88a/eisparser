"""
Model for AI extraction result.
"""

from dataclasses import asdict, dataclass
import json
import re
from typing import List, Optional


@dataclass
class AIResult:
    """Structured AI result for one purchase."""

    reg_number: str
    zakupka_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    area_min_m2: Optional[float] = None
    area_max_m2: Optional[float] = None
    rooms: Optional[str] = None
    rooms_parsed: Optional[str] = None
    floor: Optional[str] = None
    building_floors_min: Optional[str] = None
    year_build_str: Optional[str] = None
    wear_percent: Optional[float] = None
    zakazchik: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def _to_float_maybe(value) -> Optional[float]:
        """Convert tolerant numeric-like values to float.

        Handles values like "< 40", ">=47.8", "около 52", "52,5".
        Returns None for unparseable values.
        """
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        text = str(value).strip().replace(",", ".")
        if not text:
            return None

        m = re.search(r"-?\d+(?:\.\d+)?", text)
        if not m:
            return None

        try:
            return float(m.group(0))
        except ValueError:
            return None

    @classmethod
    def from_dict(cls, data: dict) -> "AIResult":
        return cls(
            reg_number=data.get("reg_number", ""),
            zakupka_name=data.get("zakupka_name"),
            address=data.get("address"),
            city=data.get("city"),
            area_min_m2=cls._to_float_maybe(data.get("area_min_m2")),
            area_max_m2=cls._to_float_maybe(data.get("area_max_m2")),
            rooms=data.get("rooms"),
            rooms_parsed=data.get("rooms_parsed"),
            floor=data.get("floor"),
            building_floors_min=data.get("building_floors_min"),
            year_build_str=data.get("year_build_str"),
            wear_percent=cls._to_float_maybe(data.get("wear_percent")),
            zakazchik=data.get("zakazchik"),
        )

    def get_rooms_list(self) -> List[int]:
        """Parse rooms_parsed into list[int]."""
        if not self.rooms_parsed:
            return []

        s = str(self.rooms_parsed).strip()

        # JSON-ish values
        try:
            parsed = json.loads(s)
            if isinstance(parsed, int):
                return [parsed]
            if isinstance(parsed, list):
                return [int(x) for x in parsed]
        except Exception:
            pass

        # Range: "1-3" or "1–3"
        range_match = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", s)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if start <= end:
                return list(range(start, end + 1))
            return list(range(end, start + 1))

        # CSV: "1,2,3"
        if "," in s:
            out = []
            for x in s.split(","):
                x = x.strip()
                if x.isdigit():
                    out.append(int(x))
            return out

        # Single int
        if s.isdigit():
            return [int(s)]

        return []
