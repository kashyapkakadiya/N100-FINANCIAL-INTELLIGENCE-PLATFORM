from __future__ import annotations
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(prefix="/sectors", tags=["sectors"])

def _get_all_sectors(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT broad_sector FROM sectors").fetchall()]

@router.get("")
def list_sectors():
    """
    All sectors with company_count, median_roe, median_pe, median_de.
    NOTE: returns however many broad sectors exist in the source data.
    sectors.xlsx has always had only 10 of the spec's 11 broad sectors -
    "Conglomerates / Other" is absent from the raw source entirely
    (documented since Sprint 1's retro, unchanged every sprint since).
    This endpoint reports the true count rather than padding to 11.
    """
    conn = get_connection()
    sector_names = _get_all_sectors(conn)
    result = []
    for sector in sector_names:
        ratios = conn.execute("""
            SELECT f.return_on_equity_pct, f.debt_to_equity FROM financial_ratios f
            JOIN sectors s ON f.company_id = s.company_id
            WHERE s.broad_sector = ? AND f.net_profit_margin_pct IS NOT NULL
            AND f.year = (SELECT MAX(f2.year) FROM financial_ratios f2
                          WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
        """, (sector,)).fetchall()
        pe_rows = conn.execute("""
            SELECT m.pe_ratio FROM market_cap m
            JOIN sectors s ON m.company_id = s.company_id
            JOIN (SELECT company_id, MAX(cal_year) AS mx FROM market_cap GROUP BY company_id) latest
                ON m.company_id = latest.company_id AND m.cal_year = latest.mx
            WHERE s.broad_sector = ?
        """, (sector,)).fetchall()

        roes = sorted(r[0] for r in ratios if r[0] is not None)
        des = sorted(r[1] for r in ratios if r[1] is not None)
        pes = sorted(r[0] for r in pe_rows if r[0] is not None)

        def median(vals):
            n = len(vals)
            if n == 0: return None
            mid = n // 2
            return vals[mid] if n % 2 else (vals[mid-1] + vals[mid]) / 2

        result.append({
            "sector": sector,
            "company_count": len(ratios),
            "median_roe": median(roes),
            "median_pe": median(pes),
            "median_de": median(des),
        })
    conn.close()
    return {"count": len(result), "sectors": result}


@router.get("/{sector}/companies")
def get_sector_companies(sector: str):
    """All companies in a sector with their latest-year KPIs. 404 for unknown sector."""
    conn = get_connection()
    if sector not in _get_all_sectors(conn):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Sector '{sector}' not found")

    rows = conn.execute("""
        SELECT f.company_id, c.company_name, s.sub_sector,
               f.return_on_equity_pct, f.return_on_capital_employed_pct,
               f.net_profit_margin_pct, f.debt_to_equity, f.revenue_cagr_5yr,
               f.free_cash_flow_cr, f.composite_quality_score
        FROM financial_ratios f
        LEFT JOIN companies c ON f.company_id = c.id
        JOIN sectors s ON f.company_id = s.company_id
        WHERE s.broad_sector = ? AND f.net_profit_margin_pct IS NOT NULL
        AND f.year = (SELECT MAX(f2.year) FROM financial_ratios f2
                      WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
        ORDER BY f.company_id
    """, (sector,)).fetchall()
    conn.close()
    return {"sector": sector, "count": len(rows), "companies": [dict(r) for r in rows]}