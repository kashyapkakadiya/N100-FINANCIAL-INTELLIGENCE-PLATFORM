from __future__ import annotations
import sys
from pathlib import Path
from fastapi import APIRouter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

CORE_KPIS = ["return_on_equity_pct", "return_on_capital_employed_pct", "net_profit_margin_pct",
             "debt_to_equity", "interest_coverage", "asset_turnover", "free_cash_flow_cr",
             "revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr"]

@router.get("/stats")
def portfolio_stats():
    """P10 through P90 percentile table for 10 core KPIs across all 92 companies."""
    conn = get_connection()
    rows_raw = conn.execute(f"""
        SELECT {', '.join(CORE_KPIS)} FROM financial_ratios f1
        WHERE net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(f2.year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """).fetchall()
    conn.close()

    import statistics
    result = []
    for i, metric in enumerate(CORE_KPIS):
        values = sorted(r[i] for r in rows_raw if r[i] is not None)
        if not values:
            result.append({"metric": metric, "P10": None, "P25": None, "P50": None, "P75": None, "P90": None})
            continue
        def pct(p):
            k = (len(values) - 1) * p
            f, c = int(k), min(int(k) + 1, len(values) - 1)
            return round(values[f] + (values[c] - values[f]) * (k - f), 2)
        result.append({
            "metric": metric, "P10": pct(0.10), "P25": pct(0.25), "P50": pct(0.50),
            "P75": pct(0.75), "P90": pct(0.90),
            "mean": round(statistics.mean(values), 2), "std": round(statistics.pstdev(values), 2),
        })
    return {"kpi_count": len(result), "stats": result}