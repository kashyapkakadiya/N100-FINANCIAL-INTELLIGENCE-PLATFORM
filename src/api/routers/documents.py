from __future__ import annotations
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from api.db import get_connection

router = APIRouter(tags=["documents"])

@router.get("/companies/{ticker}/documents")
def get_documents(ticker: str):
    """
    Annual report links with an is_url_valid flag for each.
    NOTE: is_url_valid checks well-formedness (non-null, http/https scheme),
    NOT a live HTTP check - this API server has no guaranteed outbound
    network access to bseindia.com, the same constraint documented since
    Sprint 1's DQ-13 and Sprint 4's Annual Reports dashboard screen. A live
    200-vs-404 check should be added as a background job with caching if
    genuine link-rot detection is required, not a synchronous per-request
    call that could hang the endpoint.
    """
    ticker = ticker.strip().upper()
    conn = get_connection()
    if not conn.execute("SELECT 1 FROM companies WHERE id = ?", (ticker,)).fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    rows = conn.execute(
        "SELECT report_year, annual_report FROM documents WHERE company_id = ? ORDER BY report_year DESC", (ticker,)
    ).fetchall()
    conn.close()
    records = []
    for r in rows:
        url = r["annual_report"]
        is_url_valid = bool(url and str(url).startswith(("http://", "https://")))
        records.append({"report_year": r["report_year"], "annual_report": url, "is_url_valid": is_url_valid})
    return {"company_id": ticker, "count": len(records), "records": records}