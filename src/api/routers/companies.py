"""
src/api/routers/companies.py — Module 11, Day 39: Company Data Endpoints.

roe_pct / roce_pct in the /companies list endpoint use the Ratio Engine's
computed values (financial_ratios, latest real P&L year), not
companies.roe_percentage / roce_percentage. Consistent with this project's
established convention since Sprint 2 Day 13: the source's pre-computed
values are known to be anomalous for some companies (e.g. TCS shows 0.52%
in the raw source vs the Ratio Engine's correct ~51%) and are display-only
reference values, not the analytical source of truth.
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection, LATEST_YEAR_SUBQUERY

router = APIRouter(prefix="/companies", tags=["companies"])

TEARSHEET_DIR = Path(__file__).resolve().parent.parent.parent.parent / "reports" / "tearsheets"


def _normalise_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def _company_exists(conn, ticker: str) -> bool:
    row = conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone()
    return row is not None


@router.get("")
def list_companies(
    sector: Optional[str] = Query(None, description="Filter by broad_sector"),
    market_cap_category: Optional[str] = Query(None, description="Filter by market_cap_category"),
    search: Optional[str] = Query(None, description="Partial match on company name or ticker"),
):
    """List all companies with id, name, sector, sub-sector, and latest ROE/ROCE. Supports sector, market_cap_category, and search filters."""
    conn = get_connection()
    query = """
        SELECT c.id, c.company_name, s.broad_sector, s.sub_sector, s.market_cap_category,
               f.return_on_equity_pct AS roe_pct, f.return_on_capital_employed_pct AS roce_pct
        FROM companies c
        LEFT JOIN sectors s ON c.id = s.company_id
        LEFT JOIN financial_ratios f ON c.id = f.company_id
            AND f.net_profit_margin_pct IS NOT NULL
            AND f.year = (SELECT MAX(f2.year) FROM financial_ratios f2
                          WHERE f2.company_id = c.id AND f2.net_profit_margin_pct IS NOT NULL)
        WHERE 1=1
    """
    params = []
    if sector:
        query += " AND s.broad_sector = ?"
        params.append(sector)
    if market_cap_category:
        query += " AND s.market_cap_category = ?"
        params.append(market_cap_category)
    if search:
        query += " AND (c.company_name LIKE ? OR c.id LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])
    query += " ORDER BY c.id"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {"count": len(rows), "companies": [dict(r) for r in rows]}


@router.get("/{ticker}")
def get_company(ticker: str):
    """Full company profile: all companies fields + latest-year KPIs + sector data. 404 if ticker not found."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    if not _company_exists(conn, ticker):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    company = dict(conn.execute("SELECT * FROM companies WHERE id = ?", (ticker,)).fetchone())
    sector_row = conn.execute("SELECT * FROM sectors WHERE company_id = ?", (ticker,)).fetchone()
    ratios_row = conn.execute(f"""
        SELECT * FROM financial_ratios f1 WHERE company_id = ? AND {LATEST_YEAR_SUBQUERY}
    """, (ticker,)).fetchone()
    conn.close()

    return {
        "company": company,
        "sector": dict(sector_row) if sector_row else None,
        "latest_ratios": dict(ratios_row) if ratios_row else None,
    }


def _year_filtered(conn, table: str, ticker: str, from_year: Optional[str], to_year: Optional[str]):
    query = f"SELECT * FROM {table} WHERE company_id = ?"
    params = [ticker]
    if from_year:
        query += " AND year >= ?"
        params.append(from_year)
    if to_year:
        query += " AND year <= ?"
        params.append(to_year)
    query += " ORDER BY year"
    return [dict(r) for r in conn.execute(query, params).fetchall()]


@router.get("/{ticker}/pl")
def get_profit_and_loss(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None):
    """P&L history for a company. Optional from_year/to_year filters in YYYY-MM format."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    if not _company_exists(conn, ticker):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    rows = _year_filtered(conn, "profitandloss", ticker, from_year, to_year)
    conn.close()
    return {"company_id": ticker, "count": len(rows), "records": rows}


@router.get("/{ticker}/bs")
def get_balance_sheet(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None):
    """Balance sheet history for a company. Optional from_year/to_year filters."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    if not _company_exists(conn, ticker):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    rows = _year_filtered(conn, "balancesheet", ticker, from_year, to_year)
    conn.close()
    return {"company_id": ticker, "count": len(rows), "records": rows}


@router.get("/{ticker}/cashflow")
def get_cashflow(ticker: str, from_year: Optional[str] = None, to_year: Optional[str] = None):
    """Cash flow history for a company. Optional from_year/to_year filters."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    if not _company_exists(conn, ticker):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    rows = _year_filtered(conn, "cashflow", ticker, from_year, to_year)
    conn.close()
    return {"company_id": ticker, "count": len(rows), "records": rows}


@router.get("/{ticker}/ratios")
def get_ratios(ticker: str, year: Optional[str] = None):
    """All computed KPIs per year for a company. Optional year param for a single year."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    if not _company_exists(conn, ticker):
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    if year:
        rows = conn.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ? AND net_profit_margin_pct IS NOT NULL",
            (ticker, year),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND net_profit_margin_pct IS NOT NULL ORDER BY year",
            (ticker,),
        ).fetchall()
    conn.close()
    return {"company_id": ticker, "count": len(rows), "records": [dict(r) for r in rows]}


@router.get("/{ticker}/tearsheet")
def get_tearsheet(ticker: str):
    """Returns the pre-generated 2-page tearsheet PDF as a binary download."""
    ticker = _normalise_ticker(ticker)
    conn = get_connection()
    exists = _company_exists(conn, ticker)
    conn.close()
    if not exists:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")

    pdf_path = TEARSHEET_DIR / f"{ticker}_tearsheet.pdf"
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Tearsheet not generated for '{ticker}' (likely has fewer than 3 years of data - see skipped_tearsheets.csv)",
        )
    return FileResponse(path=pdf_path, media_type="application/pdf", filename=f"{ticker}_tearsheet.pdf")