"""
normaliser.py
-------------
normalize_year(raw)   -> 'YYYY-MM' string, or None on parse failure
normalize_ticker(raw) -> uppercase, stripped NSE ticker, or None on reject
"""

from __future__ import annotations
import re
from typing import Optional

_MONTH_MAP = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

_ALREADY_NORMALISED = re.compile(r"^(\d{4})-(\d{2})$")
_MONTH_YEAR = re.compile(r"^([A-Za-z]{3,9})[\s\-]+(\d{2,4})$")
_FY_PREFIX = re.compile(r"^FY[\s\-]?(\d{2,4})$", re.IGNORECASE)
_PURE_YEAR = re.compile(r"^(\d{4})$")


def _expand_year(yy: str) -> str:
    return yy if len(yy) == 4 else f"20{yy}"


def normalize_year(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = re.sub(r"\s+", " ", s)

    m = _ALREADY_NORMALISED.match(s)
    if m:
        year, month = m.groups()
        return f"{year}-{month}" if 1 <= int(month) <= 12 else None

    m = _FY_PREFIX.match(s)
    if m:
        return f"{_expand_year(m.group(1))}-03"

    m = _MONTH_YEAR.match(s)
    if m:
        month_raw, year_raw = m.groups()
        month = _MONTH_MAP.get(month_raw.lower())
        if month is None:
            return None
        return f"{_expand_year(year_raw)}-{month}"

    m = _PURE_YEAR.match(s)
    if m:
        return f"{m.group(1)}-03"

    return None  # TTM, '2024.5', 'Mar 2016 9m', 'Mar 2023 15', etc. all land here


_TICKER_RE = re.compile(r"^[A-Z0-9&\-]{2,12}$")


def normalize_ticker(raw) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    if not s or s == "NAN":
        return None
    if not _TICKER_RE.match(s):
        return None
    return s