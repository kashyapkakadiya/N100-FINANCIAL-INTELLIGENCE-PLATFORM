"""
src/reports/portfolio_summary.py — Module 8, Day 35: Portfolio Summary PDF.

One page per company, alphabetical by ticker. 6 KPIs with trend arrows.

DESIGN DECISIONS (flagged, not silent):
1. "Improved"/"declined" is a directional judgment per metric, not a raw
   value comparison. D/E decreasing is an improvement (up arrow); ROE
   decreasing is a decline (down arrow) - each KPI has a HIGHER_IS_BETTER
   flag governing which direction counts as "up".
2. Substituted "Revenue YoY growth %" for "Revenue CAGR 5yr" as the 6th
   KPI. Sprint 2 only stores one CAGR value per company (on its latest
   row, not one per year), so there is no prior-year CAGR to compare
   against for a trend arrow. YoY revenue growth has real per-year
   continuity and is arguably more appropriate for a single-year trend
   indicator than a smoothed multi-year CAGR anyway.
3. Flat threshold is +-2% per spec ("flat within 2%"), applied to the RAW
   percentage change before the higher-is-better direction is applied.
"""
from __future__ import annotations
import sys
import sqlite3
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, green, red, grey
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUT_PATH = Path(__file__).resolve().parent.parent.parent / "reports" / "portfolio" / "portfolio_summary.pdf"

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
NAVY = HexColor("#1a2744")
LIGHT_GREY = HexColor("#f2f4f7")

KPIS = [
    ("ROE", "return_on_equity_pct", True, "%"),
    ("ROCE", "return_on_capital_employed_pct", True, "%"),
    ("Net Profit Margin", "net_profit_margin_pct", True, "%"),
    ("Debt/Equity", "debt_to_equity", False, ""),
    ("Revenue YoY Growth", "_revenue_yoy_pct", True, "%"),  # computed, not a stored column
    ("Free Cash Flow", "free_cash_flow_cr", True, " Cr"),
]
FLAT_THRESHOLD_PCT = 2.0


def load_all_company_history(conn) -> pd.DataFrame:
    ratios = pd.read_sql("""
        SELECT company_id, year, return_on_equity_pct, return_on_capital_employed_pct,
               net_profit_margin_pct, debt_to_equity, free_cash_flow_cr
        FROM financial_ratios WHERE net_profit_margin_pct IS NOT NULL ORDER BY company_id, year
    """, conn)
    pl = pd.read_sql("SELECT company_id, year, sales FROM profitandloss ORDER BY company_id, year", conn)
    merged = ratios.merge(pl, on=["company_id", "year"], how="left")
    merged["_revenue_yoy_pct"] = merged.groupby("company_id")["sales"].pct_change() * 100
    return merged


def trend_arrow(current, previous, higher_is_better: bool) -> tuple[str, object]:
    """Returns (symbol, color). previous=None means no comparison possible."""
    if current is None or pd.isna(current) or previous is None or pd.isna(previous):
        return "N/A", grey

    if previous == 0:
        if current == 0:
            return "\u2192", grey
        pct_change = 100.0 if current > 0 else -100.0
    else:
        pct_change = (current - previous) / abs(previous) * 100

    if abs(pct_change) <= FLAT_THRESHOLD_PCT:
        return "\u2192", grey

    improved = (pct_change > 0) if higher_is_better else (pct_change < 0)
    return ("\u2191", green) if improved else ("\u2193", red)


def build_portfolio_summary():
    conn = sqlite3.connect(DB_PATH)
    companies = pd.read_sql("SELECT id, company_name FROM companies ORDER BY id", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    history = load_all_company_history(conn)
    conn.close()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT_PATH), pagesize=A4)

    pages_built = 0
    for _, row in companies.iterrows():
        cid, name = row["id"], row["company_name"]
        company_hist = history[history["company_id"] == cid].sort_values("year")
        if company_hist.empty:
            continue  # no real P&L year at all - nothing to show

        sector_row = sectors[sectors["company_id"] == cid]
        sector = sector_row.iloc[0]["broad_sector"] if len(sector_row) else "N/A"

        latest = company_hist.iloc[-1]
        previous = company_hist.iloc[-2] if len(company_hist) >= 2 else None

        c.setFillColor(NAVY)
        c.rect(0, PAGE_H - 28 * mm, PAGE_W, 28 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(MARGIN, PAGE_H - 14 * mm, str(name)[:55])
        c.setFont("Helvetica", 11)
        c.drawString(MARGIN, PAGE_H - 21 * mm, f"{cid}  |  {sector}")

        y_top = PAGE_H - 40 * mm
        tile_w = (PAGE_W - 2 * MARGIN - 2 * 6 * mm) / 3
        tile_h = 22 * mm
        gap = 6 * mm

        for i, (label, col, higher_is_better, suffix) in enumerate(KPIS):
            row_i, col_i = divmod(i, 3)
            x = MARGIN + col_i * (tile_w + gap)
            y = y_top - row_i * (tile_h + gap) - tile_h

            cur_val = latest.get(col)
            prev_val = previous.get(col) if previous is not None else None
            arrow, arrow_color = trend_arrow(cur_val, prev_val, higher_is_better)

            c.setFillColor(LIGHT_GREY)
            c.roundRect(x, y, tile_w, tile_h, 3, fill=1, stroke=0)
            c.setFillColor(NAVY)
            c.setFont("Helvetica", 8)
            c.drawString(x + 4, y + tile_h - 10, label)

            value_str = f"{cur_val:.1f}{suffix}" if pd.notna(cur_val) else "N/A"
            c.setFont("Helvetica-Bold", 15)
            c.drawString(x + 4, y + 6, value_str)

            c.setFillColor(arrow_color)
            c.setFont("Helvetica-Bold", 16)
            c.drawRightString(x + tile_w - 4, y + 6, arrow)

        c.setFont("Helvetica", 7)
        c.setFillColor(HexColor("#666666"))
        c.drawString(MARGIN, 10 * mm, f"Portfolio Summary — {cid} — as of {latest['year']}")

        c.showPage()
        pages_built += 1

    c.save()
    return pages_built


if __name__ == "__main__":
    n_pages = build_portfolio_summary()
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"portfolio_summary.pdf: {n_pages} pages, {size_kb:.0f} KB")