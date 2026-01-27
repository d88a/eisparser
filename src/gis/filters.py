# gis/filters.py
"""Utility functions for building 2GIS URL filter fragments.

This module provides normalization helpers and fragment builders that are used by
`build_2gis_realty_url` in ``gis/generator.py``.
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any

# Mapping from room count to 2GIS ID.
# See kb/reports/REPORT_2GIS_ROOM_IDS.md for documentation.
ROOMS_TO_2GIS_ID: Dict[int, str] = {
    1: "4181700697707238747",
    2: "9052824901306559087",
    3: "14883364286970164480",
    4: "13648940551269033600",
    5: "4391054652267765575",
}

# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _to_float(v: Any) -> Optional[float]:
    """Convert *v* to ``float`` if possible, otherwise ``None``.

    ``None`` is also returned for empty strings or values that cannot be parsed.
    """
    if v is None:
        return None
    if isinstance(v, float):
        return v
    if isinstance(v, int):
        return float(v)
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


def normalize_float(v: Any) -> Optional[float]:
    """Public wrapper for ``_to_float`` – kept for backward compatibility."""
    return _to_float(v)


def normalize_int(v: Any) -> Optional[int]:
    """Convert *v* to ``int`` if possible, otherwise ``None``.

    Floats are truncated toward zero, strings are stripped and parsed.
    """
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    try:
        return int(str(v).strip())
    except (ValueError, TypeError):
        return None


def normalize_rooms_counts(v: Any) -> Optional[List[int]]:
    """Accept ``int``, ``list[int]`` or JSON‑style string ``"[2,3]"``.

    Returns a sorted list of unique room counts or ``None`` if the input is
    invalid/empty.
    """
    if v is None:
        return None
    # Single integer – treat as a one‑element list
    if isinstance(v, int):
        return [v]
    # Already a list/tuple of ints
    if isinstance(v, (list, tuple)):
        try:
            ints = [int(x) for x in v]
            return sorted(set(ints))
        except Exception:
            return None
    # JSON‑like string
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                import json
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    ints = [int(x) for x in parsed]
                    return sorted(set(ints))
            except Exception:
                return None
    return None

# ---------------------------------------------------------------------------
# Fragment builders
# ---------------------------------------------------------------------------

def build_range_fragment(slug: str, vmin: Optional[float], vmax: Optional[float]) -> Optional[str]:
    """Build a ``slug=min,max`` fragment.

    - If both *vmin* and *vmax* are ``None`` → ``None``.
    - If only one side is present → ``slug=value,`` (min) or ``slug=,value`` (max).
    - If both are present and ``vmin > vmax`` they are swapped.
    """
    if vmin is None and vmax is None:
        return None
    # Normalise to floats for comparison
    if vmin is not None:
        vmin = float(vmin)
    if vmax is not None:
        vmax = float(vmax)
    if vmin is not None and vmax is not None and vmin > vmax:
        vmin, vmax = vmax, vmin
    # Build string – note that commas must be URL‑encoded later (handled by caller)
    if vmin is None:
        fragment = f"{slug}=,{int(vmax)}"
    elif vmax is None:
        fragment = f"{slug}={int(vmin)},"
    else:
        fragment = f"{slug}={int(vmin)},{int(vmax)}"
    return fragment


def build_komnat_fragment(rooms_counts: List[int]) -> Optional[str]:
    """Create ``komnat%3D<ID1>%2C<ID2>`` fragment.

    ``rooms_counts`` must be a list of ints. The function looks up each count in
    ``ROOMS_TO_2GIS_ID`` and joins the IDs with commas. If any count is missing
    from the mapping, the fragment is omitted (``None``) – the caller can decide
    how to handle it.
    """
    if not rooms_counts:
        return None
    ids: List[str] = []
    for rc in rooms_counts:
        id_ = ROOMS_TO_2GIS_ID.get(rc)
        if not id_:
            # Missing mapping – abort fragment creation
            return None
        ids.append(id_)
    joined = ",".join(ids)
    return f"komnat={joined}"


def join_fragments(fragments: List[str]) -> str:
    """Join a list of filter fragments with ``;`` (semicolon).

    The caller is responsible for URL‑encoding the semicolon as ``%3B`` when
    constructing the final URL.
    """
    return ";".join(fragments)

# End of file
