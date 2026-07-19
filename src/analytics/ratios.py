"""
ratios.py — Module 2: Profitability, Leverage & Efficiency Ratios (Day 8-9)

All functions take scalar inputs and return a single value (or None on an
edge case) so they're independently unit-testable. A batch runner at the
bottom applies them row-wise to the joined P&L + Balance Sheet data.
"""

from __future__ import annotations
from typing import Optional


# ---------------------------------------------------------------------------
# Day 8 — Profitability Ratios
# ---------------------------------------------------------------------------

def net_profit_margin(sales: float, net_profit: float) -> Optional[float]:
    """NPM = net_profit / sales x 100. None if sales = 0."""
    if sales is None or sales == 0:
        return None
    return (net_profit / sales) * 100


def operating_profit_margin(sales: float, operating_profit: float) -> Optional[float]:
    """Computed OPM = operating_profit / sales x 100. None if sales = 0."""
    if sales is None or sales == 0:
        return None
    return (operating_profit / sales) * 100


def opm_cross_check(computed_opm: Optional[float], reported_opm: Optional[float]) -> Optional[float]:
    """Returns the absolute difference between computed and reported OPM, or None if either is missing."""
    if computed_opm is None or reported_opm is None:
        return None
    return abs(computed_opm - reported_opm)


def return_on_equity(net_profit: float, equity_capital: float, reserves: float) -> Optional[float]:
    """ROE = net_profit / (equity_capital + reserves) x 100. None if equity+reserves <= 0."""
    equity = (equity_capital or 0) + (reserves or 0)
    if equity <= 0:
        return None
    return (net_profit / equity) * 100


def ebit(operating_profit: float, depreciation: float) -> float:
    """EBIT = operating_profit - depreciation."""
    return operating_profit - (depreciation or 0)


def return_on_capital_employed(operating_profit: float, depreciation: float,
                                 equity_capital: float, reserves: float,
                                 borrowings: float) -> Optional[float]:
    """
    ROCE = EBIT / (equity + reserves + borrowings) x 100.
    None if the capital employed base is <= 0.
    NOTE: for Financials-sector companies, compare this value against a
    sector-relative benchmark rather than the universal >15%/>25% threshold
    (see analytics/sector_roce_notes — Day 13) — this function still computes
    the raw number the same way for every company; the benchmark interpretation
    differs, not the formula.
    """
    capital_employed = (equity_capital or 0) + (reserves or 0) + (borrowings or 0)
    if capital_employed <= 0:
        return None
    return (ebit(operating_profit, depreciation) / capital_employed) * 100


def return_on_assets(net_profit: float, total_assets: float) -> Optional[float]:
    """ROA = net_profit / total_assets x 100. None if total_assets = 0."""
    if total_assets is None or total_assets == 0:
        return None
    return (net_profit / total_assets) * 100


# ---------------------------------------------------------------------------
# Day 9 — Leverage & Efficiency Ratios
# ---------------------------------------------------------------------------

def debt_to_equity(borrowings: float, equity_capital: float, reserves: float) -> Optional[float]:
    """
    D/E = borrowings / (equity_capital + reserves).
    Returns 0 (not None) if borrowings = 0 — debt-free is a real, valid value.
    Returns None only if borrowings > 0 but the equity base is <= 0 (can't compute).
    """
    if borrowings is None or borrowings == 0:
        return 0
    equity = (equity_capital or 0) + (reserves or 0)
    if equity <= 0:
        return None
    return borrowings / equity


def high_leverage_flag(de: Optional[float], broad_sector: str) -> bool:
    """True if D/E > 5 and the company is NOT in the Financials sector."""
    if de is None:
        return False
    return de > 5 and broad_sector != "Financials"


def interest_coverage(operating_profit: float, other_income: float, interest: float):
    """
    ICR = (operating_profit + other_income) / interest.
    Returns (icr_value, icr_label). icr_value is None if interest = 0 (debt-free),
    and icr_label is 'Debt Free' in that case, else the rounded numeric string.
    """
    other_income = other_income or 0
    if interest is None or interest == 0:
        return None, "Debt Free"
    icr = (operating_profit + other_income) / interest
    return icr, f"{icr:.2f}"


def icr_risk_flag(icr: Optional[float]) -> bool:
    """True if ICR < 1.5 (at risk of not covering interest payments)."""
    if icr is None:
        return False
    return icr < 1.5


def net_debt(borrowings: float, investments: float) -> float:
    """Net Debt = borrowings - investments (investments used as liquid asset proxy)."""
    return (borrowings or 0) - (investments or 0)


def asset_turnover(sales: float, total_assets: float) -> Optional[float]:
    """Asset Turnover = sales / total_assets. None if total_assets = 0."""
    if total_assets is None or total_assets == 0:
        return None
    return sales / total_assets