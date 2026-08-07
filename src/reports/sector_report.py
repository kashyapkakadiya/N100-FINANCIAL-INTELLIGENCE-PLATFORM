"""
src/reports/sector_report.py — Module 8, Day 34: Sector Report Generator.

NOTE: generates 10 sector PDFs, not 11. sectors.xlsx has always had only
10 of the spec's 11 broad sectors - "Conglomerates / Other" is absent from
the raw source data entirely (documented in Sprint 1's retro and every
sprint since). This is not a bug in this script.
"""
from __future__ import annotations
import sys
import sqlite3
from pathlib import Path

import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "reports" / "sector"

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
NAVY = HexColor("#1a2744")
LIGHT_GREY = HexColor("#f2f4f7")

styles = getSampleStyleSheet()
cell_style = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=9)
header_cell_style = ParagraphStyle("header_cell", parent=styles["Normal"], fontSize=7, leading=9, textColor=white)


def load_sector_data(conn, sector: str) -> pd.DataFrame:
    df = pd.read_sql("""
        SELECT f.company_id, c.company_name, f.return_on_equity_pct, f.return_on_capital_employed_pct,
               f.net_profit_margin_pct, f.debt_to_equity, f.revenue_cagr_5yr, f.pat_cagr_5yr,
               f.free_cash_flow_cr, f.composite_quality_score
        FROM financial_ratios f
        JOIN sectors s ON f.company_id = s.company_id
        LEFT JOIN companies c ON f.company_id = c.id
        WHERE s.broad_sector = ? AND f.net_profit_margin_pct IS NOT NULL
        AND f.year = (SELECT MAX(year) FROM financial_ratios f2
                      WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
        ORDER BY f.company_id
    """, conn, params=(sector,))
    return df


def build_sector_pdf(sector: str, conn):
    df = load_sector_data(conn, sector)
    if df.empty:
        return False, "No companies found for this sector"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sector.replace(" / ", "_").replace(" ", "_").replace("/", "_")
    out_path = OUTPUT_DIR / f"{safe_name}_report.pdf"
    c = canvas.Canvas(str(out_path), pagesize=A4)

    # Header
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 28 * mm, PAGE_W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, PAGE_H - 15 * mm, sector)
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN, PAGE_H - 22 * mm, f"{len(df)} companies — Sector Summary Report")

    # Median KPI tiles
    medians = {
        "Median ROE": f"{df['return_on_equity_pct'].median():.1f}%",
        "Median ROCE": f"{df['return_on_capital_employed_pct'].median():.1f}%",
        "Median NPM": f"{df['net_profit_margin_pct'].median():.1f}%",
        "Median D/E": f"{df['debt_to_equity'].median():.2f}",
        "Median Rev CAGR 5yr": f"{df['revenue_cagr_5yr'].median():.1f}%" if df['revenue_cagr_5yr'].notna().any() else "N/A",
        "Median Composite Score": f"{df['composite_quality_score'].median():.1f}",
    }
    tile_w = (PAGE_W - 2 * MARGIN - 2 * 6 * mm) / 3
    tile_h = 16 * mm
    gap = 6 * mm
    y_top = PAGE_H - 34 * mm
    for i, (label, value) in enumerate(medians.items()):
        row, col = divmod(i, 3)
        x = MARGIN + col * (tile_w + gap)
        y = y_top - row * (tile_h + gap) - tile_h
        c.setFillColor(LIGHT_GREY)
        c.roundRect(x, y, tile_w, tile_h, 3, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 7)
        c.drawString(x + 4, y + tile_h - 9, label)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x + 4, y + 4, value)

    table_y_top = y_top - 2 * (tile_h + gap) - 10 * mm

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(MARGIN, table_y_top, "Companies in Sector — 8 Metrics")

    headers = ["Ticker", "Company", "ROE %", "ROCE %", "NPM %", "D/E", "Rev CAGR%", "Score"]
    rows = [[Paragraph(h, header_cell_style) for h in headers]]
    for _, r in df.iterrows():
        def f(v, d=1):
            return f"{v:.{d}f}" if pd.notna(v) else "N/A"
        rows.append([
            Paragraph(str(r["company_id"]), cell_style),
            Paragraph(str(r["company_name"])[:28] if pd.notna(r["company_name"]) else "", cell_style),
            Paragraph(f(r["return_on_equity_pct"]), cell_style),
            Paragraph(f(r["return_on_capital_employed_pct"]), cell_style),
            Paragraph(f(r["net_profit_margin_pct"]), cell_style),
            Paragraph(f(r["debt_to_equity"], 2), cell_style),
            Paragraph(f(r["revenue_cagr_5yr"]), cell_style),
            Paragraph(f(r["composite_quality_score"]), cell_style),
        ])

    col_widths = [20 * mm, 48 * mm, 16 * mm, 16 * mm, 16 * mm, 14 * mm, 20 * mm, 16 * mm]
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GREY]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    avail_height = table_y_top - 15 * mm
    tw, th = table.wrap(sum(col_widths), avail_height)

    if th <= avail_height:
        table.drawOn(c, MARGIN, table_y_top - th - 5 * mm)
    else:
        # Split across a second page if the company list is too long for one page
        rows_that_fit = max(1, int((avail_height / th) * (len(rows) - 1)))
        first_part = Table(rows[:rows_that_fit + 1], colWidths=col_widths, repeatRows=1)
        first_part.setStyle(table.style)
        fw, fh = first_part.wrap(sum(col_widths), avail_height)
        first_part.drawOn(c, MARGIN, table_y_top - fh - 5 * mm)

        c.showPage()
        c.setFillColor(NAVY)
        c.rect(0, PAGE_H - 28 * mm, PAGE_W, 28 * mm, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(MARGIN, PAGE_H - 15 * mm, f"{sector} (continued)")

        second_part = Table([rows[0]] + rows[rows_that_fit + 1:], colWidths=col_widths, repeatRows=1)
        second_part.setStyle(table.style)
        sw, sh = second_part.wrap(sum(col_widths), PAGE_H - 40 * mm)
        second_part.drawOn(c, MARGIN, PAGE_H - 34 * mm - sh)

    c.showPage()
    c.save()
    return True, str(out_path)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    sectors = pd.read_sql("SELECT DISTINCT broad_sector FROM sectors ORDER BY broad_sector", conn)["broad_sector"].tolist()
    print(f"Found {len(sectors)} sectors in source data (spec expects 11 - see module docstring)")
    print()
    for sector in sectors:
        ok, msg = build_sector_pdf(sector, conn)
        if ok:
            size_kb = Path(msg).stat().st_size / 1024
            print(f"{sector}: OK ({size_kb:.0f} KB)")
        else:
            print(f"{sector}: FAILED - {msg}")
    conn.close()