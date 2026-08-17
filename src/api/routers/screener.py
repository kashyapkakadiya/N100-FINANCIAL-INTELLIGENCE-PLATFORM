from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(tags=["screener"])

@router.get("/screener")
def screener(
    min_roe: Optional[float] = Query(None),
    max_de: Optional[float] = Query(None),
    min_fcf: Optional[float] = Query(None),
    sector: Optional[str] = Query(None),
    min_rev_cagr_5yr: Optional[float] = Query(None),
    min_pat_cagr_5yr: Optional[float] = Query(None),
    max_pe: Optional[float] = Query(None),
):
    """Screener: filter companies by ROE/D-E/FCF/sector/CAGR/P-E. Returns ranked list. 400 for invalid parameter values."""
    for name, val in [("min_roe", min_roe), ("max_de", max_de), ("min_fcf", min_fcf),
                       ("min_rev_cagr_5yr", min_rev_cagr_5yr), ("min_pat_cagr_5yr", min_pat_cagr_5yr), ("max_pe", max_pe)]:
        if val is not None and not isinstance(val, (int, float)):
            raise HTTPException(status_code=400, detail=f"Invalid value for '{name}'")
    if max_de is not None and max_de < 0:
        raise HTTPException(status_code=400, detail="max_de cannot be negative")
    if min_roe is not None and min_roe < -100:
        raise HTTPException(status_code=400, detail="min_roe out of plausible range")

    conn = get_connection()
    query = """
        SELECT f.company_id, c.company_name, s.broad_sector,
               f.return_on_equity_pct, f.debt_to_equity, f.free_cash_flow_cr,
               f.revenue_cagr_5yr, f.pat_cagr_5yr, f.composite_quality_score,
               m.pe_ratio
        FROM financial_ratios f
        LEFT JOIN companies c ON f.company_id = c.id
        LEFT JOIN sectors s ON f.company_id = s.company_id
        LEFT JOIN (
            SELECT company_id, pe_ratio, cal_year,
                   ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY cal_year DESC) rn
            FROM market_cap
        ) m ON f.company_id = m.company_id AND m.rn = 1
        WHERE f.net_profit_margin_pct IS NOT NULL
        AND f.year = (SELECT MAX(f2.year) FROM financial_ratios f2
                      WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """
    params = []
    if min_roe is not None:
        query += " AND f.return_on_equity_pct >= ?"; params.append(min_roe)
    if max_de is not None:
        query += " AND (f.debt_to_equity <= ? OR s.broad_sector = 'Financials')"; params.append(max_de)
    if min_fcf is not None:
        query += " AND f.free_cash_flow_cr >= ?"; params.append(min_fcf)
    if sector:
        query += " AND s.broad_sector = ?"; params.append(sector)
    if min_rev_cagr_5yr is not None:
        query += " AND f.revenue_cagr_5yr >= ?"; params.append(min_rev_cagr_5yr)
    if min_pat_cagr_5yr is not None:
        query += " AND f.pat_cagr_5yr >= ?"; params.append(min_pat_cagr_5yr)
    if max_pe is not None:
        query += " AND m.pe_ratio <= ?"; params.append(max_pe)
    query += " ORDER BY f.composite_quality_score DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "companies": [dict(r) for r in rows]}