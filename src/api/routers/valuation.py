from __future__ import annotations
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(tags=["valuation"])

@router.get("/market-cap/{ticker}")
def get_market_cap(ticker: str):
    """Historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) from 2019-2024."""
    ticker = ticker.strip().upper()
    conn = get_connection()
    if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    rows = conn.execute(
        "SELECT cal_year, market_cap_crore, enterprise_value_crore, pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct "
        "FROM market_cap WHERE company_id = ? ORDER BY cal_year", (ticker,)
    ).fetchall()
    conn.close()
    return {"company_id": ticker, "count": len(rows), "records": [dict(r) for r in rows]}