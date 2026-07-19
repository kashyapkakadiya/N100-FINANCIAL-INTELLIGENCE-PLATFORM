"""
cashflow_kpis.py — Module 2: Cash Flow KPIs & Capital Allocation (Day 11)
"""

from __future__ import annotations
from typing import Optional, List, Dict


def free_cash_flow(operating_activity: float, investing_activity: float) -> float:
    """FCF = CFO + CFI. Negative is allowed (real, meaningful value)."""
    return (operating_activity or 0) + (investing_activity or 0)


def cfo_quality_score(cfo_values: List[float], pat_values: List[float]) -> Optional[str]:
    """
    CFO/PAT ratio averaged over up to 5 years.
    cfo_values, pat_values: same-length lists, most recent last, already
    aligned by year (caller's responsibility).
    Returns None if there's no valid PAT to divide by in any year.
    """
    ratios = []
    for cfo, pat in zip(cfo_values, pat_values):
        if pat is None or pat == 0:
            continue
        ratios.append(cfo / pat)
    if not ratios:
        return None
    avg_ratio = sum(ratios) / len(ratios)
    if avg_ratio > 1.0:
        return "High Quality"
    elif avg_ratio >= 0.5:
        return "Moderate"
    else:
        return "Accrual Risk"


def capex_intensity(investing_activity: float, sales: float) -> Optional[Dict]:
    """
    CapEx Intensity = abs(investing_activity) / sales x 100.
    Returns {'value': pct, 'label': ...} or None if sales = 0.
    """
    if sales is None or sales == 0:
        return None
    pct = abs(investing_activity) / sales * 100
    if pct < 3:
        label = "Asset Light"
    elif pct <= 8:
        label = "Moderate"
    else:
        label = "Capital Intensive"
    return {"value": pct, "label": label}


def fcf_conversion_rate(fcf: float, operating_profit: float) -> Optional[float]:
    """FCF Conversion = FCF / operating_profit x 100. None if operating_profit = 0."""
    if operating_profit is None or operating_profit == 0:
        return None
    return (fcf / operating_profit) * 100


# ---------------------------------------------------------------------------
# 8-pattern capital allocation classifier
# ---------------------------------------------------------------------------

_PATTERN_LABELS = {
    ("+", "-", "-"): "Reinvestor",              # base case for (+,-,-); Shareholder
                                                  # Returns is a sub-classification of
                                                  # this same sign pattern, applied below
    ("+", "+", "-"): "Liquidating Assets",
    ("-", "+", "+"): "Distress Signal",
    ("-", "-", "+"): "Growth Funded by Debt",
    ("+", "+", "+"): "Cash Accumulator",
    ("-", "-", "-"): "Pre-Revenue",
    ("+", "-", "+"): "Mixed",
}


def _sign(x: float) -> str:
    if x is None:
        return "0"
    if x > 0:
        return "+"
    if x < 0:
        return "-"
    return "0"


def classify_capital_allocation(cfo: float, cfi: float, cff: float,
                                  cfo_pat_ratio: Optional[float] = None) -> Dict:
    """
    Classifies a company-year into one of 8 capital-allocation patterns based
    on the sign of (CFO, CFI, CFF).

    The spec defines (+,-,-) as BOTH 'Reinvestor' and 'Shareholder Returns' —
    the same sign pattern, distinguished by whether CFO/PAT is high (mature,
    cash-generative -> paying dividends/buybacks = Shareholder Returns) or
    not yet clearly high (still plowing cash back in = Reinvestor). We use
    cfo_pat_ratio > 1.0 as that sub-classification threshold, matching the
    CFO Quality Score's own 'High Quality' cutoff for consistency. Rows with
    a sign combination the spec didn't define (e.g. containing a zero) fall
    back to 'Unclassified' rather than guessing.
    """
    signs = (_sign(cfo), _sign(cfi), _sign(cff))

    if signs == ("+", "-", "-"):
        if cfo_pat_ratio is not None and cfo_pat_ratio > 1.0:
            label = "Shareholder Returns"
        else:
            label = "Reinvestor"
    else:
        label = _PATTERN_LABELS.get(signs, "Unclassified")

    return {
        "cfo_sign": signs[0], "cfi_sign": signs[1], "cff_sign": signs[2],
        "pattern_label": label,
    }