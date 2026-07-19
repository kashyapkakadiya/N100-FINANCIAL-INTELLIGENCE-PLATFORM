"""
cagr.py — Module 2: CAGR Engine (Day 10)

compute_cagr() is the core formula with all 6 edge cases from the spec's
decision table. compute_cagr_for_window() is the application-level wrapper
that picks the right start/end values out of a company's actual year-value
history for a given window (3/5/10yr).
"""

from __future__ import annotations
from typing import Optional, Tuple, Dict


def compute_cagr(start_value: Optional[float], end_value: Optional[float],
                  n_years: Optional[int]) -> Tuple[Optional[float], Optional[str]]:
    """
    CAGR = ((end/start)^(1/n) - 1) x 100

    Returns (cagr_value, flag). flag is None when a normal value was computed.
    Edge cases (per project spec decision table):
        start missing / n_years missing or <=0        -> None, 'INSUFFICIENT'
        start == 0                                     -> None, 'ZERO_BASE'
        start > 0, end < 0                              -> None, 'DECLINE_TO_LOSS'
        start < 0, end > 0                              -> None, 'TURNAROUND'
        start < 0, end < 0                              -> None, 'BOTH_NEGATIVE'
        start > 0, end >= 0 (includes end == 0)          -> computed normally
    """
    if start_value is None or end_value is None or n_years is None or n_years <= 0:
        return None, "INSUFFICIENT"

    if start_value == 0:
        return None, "ZERO_BASE"

    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"

    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"

    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    # Remaining case: start > 0, end >= 0 (a decline to exactly zero is a
    # legitimate -100% CAGR, not a special flag)
    cagr = ((end_value / start_value) ** (1 / n_years) - 1) * 100
    return cagr, None


def compute_cagr_for_window(year_value_series: Dict[str, float],
                              window_years: int) -> Tuple[Optional[float], Optional[str]]:
    """
    year_value_series: {'YYYY-MM': value, ...} for ONE company, ONE metric
                        (e.g. all of TCS's 'sales' values keyed by year).
    window_years: 3, 5, or 10.

    Finds the latest year present and the year exactly `window_years` before
    it. If that earlier year isn't in the series (insufficient history),
    returns (None, 'INSUFFICIENT') rather than guessing with a nearby year.
    """
    if not year_value_series:
        return None, "INSUFFICIENT"

    years_sorted = sorted(year_value_series.keys())
    latest_year_str = years_sorted[-1]
    latest_year_num = int(latest_year_str[:4])
    target_start_year_num = latest_year_num - window_years

    # Match on the calendar year prefix (month can differ slightly for
    # non-March-end companies; see Sprint 1 retro note on SIEMENS-style FYs)
    start_candidates = [y for y in years_sorted if y.startswith(str(target_start_year_num))]
    if not start_candidates:
        return None, "INSUFFICIENT"

    start_year_str = start_candidates[0]
    start_value = year_value_series[start_year_str]
    end_value = year_value_series[latest_year_str]

    return compute_cagr(start_value, end_value, window_years)