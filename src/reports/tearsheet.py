"""
src/reports/tearsheet.py — Module 8, Day 33: 2-page Company Tearsheet.

IMPORTANT — found during testing: the Rupee symbol (₹) renders as a solid
black box in ReportLab's built-in fonts (they only support WinAnsi
encoding, same class of issue as the Unicode subscript/superscript warning
in the pdf skill). "Rs." is used throughout instead of ₹ - do not
reintroduce ₹ anywhere in this file or its charts.

Charts are rendered with matplotlib to in-memory PNG buffers and embedded
via canvas.drawImage(), since precise multi-series/dual-axis charts are
far more reliable this way than raw ReportLab drawing primitives.

Table cells that could contain long text (pros/cons) use reportlab
Paragraph objects inside Tables, which wordwrap automatically - never
raw drawString for variable-length text, which would silently overflow.
"""
from __future__ import annotations
import sys
import io
import sqlite3
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "reports" / "tearsheets"

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
NAVY = HexColor("#1a2744")
LIGHT_GREY = HexColor("#f2f4f7")
GREEN = HexColor("#1a7f37")
RED = HexColor("#cf222e")
GOLD = HexColor("#d4a017")

styles = getSampleStyleSheet()
wrap_style = ParagraphStyle("wrap", parent=styles["Normal"], fontSize=8, leading=10)
pro_style = ParagraphStyle("pro", parent=styles["Normal"], fontSize=9, leading=12, textColor=GREEN)
con_style = ParagraphStyle("con", parent=styles["Normal"], fontSize=9, leading=12, textColor=RED)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tearsheet_data(conn, ticker: str):
    company = pd.read_sql("SELECT * FROM companies WHERE id = ?", conn, params=(ticker,))
    if company.empty:
        return None
    company = company.iloc[0]

    sector_row = pd.read_sql("SELECT broad_sector, sub_sector FROM sectors WHERE company_id = ?", conn, params=(ticker,))
    sector = sector_row.iloc[0]["broad_sector"] if len(sector_row) else "N/A"

    pl = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    bs = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    cf = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    ratios = pd.read_sql("""
        SELECT * FROM financial_ratios WHERE company_id = ? AND net_profit_margin_pct IS NOT NULL ORDER BY year
    """, conn, params=(ticker,))

    pros_cons = None
    pc_path = Path(__file__).resolve().parent.parent.parent / "output" / "pros_cons_generated.csv"
    if pc_path.exists():
        all_pc = pd.read_csv(pc_path)
        pros_cons = all_pc[all_pc["company_id"] == ticker]

    return {
        "ticker": ticker, "company": company, "sector": sector,
        "pl": pl, "bs": bs, "cf": cf, "ratios": ratios, "pros_cons": pros_cons,
    }


# ---------------------------------------------------------------------------
# Chart builders (matplotlib -> PNG bytes)
# ---------------------------------------------------------------------------

def _fig_to_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_revenue_profit(pl: pd.DataFrame):
    plot_df = pl.tail(10)
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    ax.ticklabel_format(style="plain", axis="y")
    x = range(len(plot_df))
    ax.bar([i - 0.2 for i in x], plot_df["sales"], width=0.4, label="Revenue", color="#1a2744")
    ax.bar([i + 0.2 for i in x], plot_df["net_profit"], width=0.4, label="Net Profit", color="#4a90d9")
    ax.set_xticks(list(x))
    ax.set_xticklabels([y[:4] for y in plot_df["year"]], fontsize=7, rotation=45)
    ax.set_ylabel("Rs. Cr", fontsize=8)
    ax.set_title("Revenue & Net Profit (10yr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    return _fig_to_buf(fig)


def chart_roe_roce(ratios: pd.DataFrame):
    plot_df = ratios.tail(10)
    fig, ax1 = plt.subplots(figsize=(4.6, 2.6))
    ax1.ticklabel_format(style="plain", axis="y")
    ax2 = ax1.twinx()
    x = range(len(plot_df))
    ax1.plot(x, plot_df["return_on_equity_pct"], marker="o", markersize=3, color="#1a2744", label="ROE %")
    ax2.plot(x, plot_df["return_on_capital_employed_pct"], marker="s", markersize=3, color="#d4a017", label="ROCE %")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([y[:4] for y in plot_df["year"]], fontsize=7, rotation=45)
    ax1.set_ylabel("ROE %", fontsize=8, color="#1a2744")
    ax2.set_ylabel("ROCE %", fontsize=8, color="#d4a017")
    ax1.set_title("ROE & ROCE Trend (10yr)", fontsize=9)
    ax1.tick_params(labelsize=7)
    ax2.tick_params(labelsize=7)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")
    fig.tight_layout()
    return _fig_to_buf(fig)


def chart_bs_composition(bs: pd.DataFrame, valid_years: set):
    """
    valid_years: the company's real P&L years (from data['pl']['year']).
    Found during visual QA: without this filter, TCS's chart showed two
    bars both labelled '2024' (the real 2024-03 annual close plus the
    interim 2024-09 balance-sheet-only snapshot) - the same recurring
    "latest year" trap hit five times now across this project. Balance
    sheet history is filtered to years that also have real P&L data before
    charting, not just .tail(10) on the raw table.
    """
    plot_df = bs[bs["year"].isin(valid_years)].tail(10)
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.ticklabel_format(style="plain", axis="y")
    x = range(len(plot_df))
    equity = plot_df["equity_capital"].fillna(0) + plot_df["reserves"].fillna(0)
    borrowings = plot_df["borrowings"].fillna(0)
    other = plot_df["other_liabilities"].fillna(0)
    ax.bar(x, equity, label="Equity + Reserves", color="#1a2744")
    ax.bar(x, borrowings, bottom=equity, label="Borrowings", color="#cf222e")
    ax.bar(x, other, bottom=equity + borrowings, label="Other Liabilities", color="#9aa5b1")
    ax.set_xticks(list(x))
    ax.set_xticklabels([y[:4] for y in plot_df["year"]], fontsize=7, rotation=45)
    ax.set_ylabel("Rs. Cr", fontsize=8)
    ax.set_title("Balance Sheet Composition (10yr)", fontsize=9)
    ax.legend(fontsize=7)
    ax.tick_params(labelsize=7)
    fig.tight_layout()
    return _fig_to_buf(fig)


def chart_cashflow_waterfall(cf: pd.DataFrame):
    if cf.empty:
        return None
    latest = cf.iloc[-1]
    labels = ["CFO", "CFI", "CFF", "Net Change"]
    values = [latest["operating_activity"], latest["investing_activity"],
              latest["financing_activity"], latest["net_cash_flow"]]
    colors = ["#1a7f37" if v is not None and v >= 0 else "#cf222e" for v in values]
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    ax.ticklabel_format(style="plain", axis="y")
    ax.bar(labels, [v if v is not None else 0 for v in values], color=colors)
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_ylabel("Rs. Cr", fontsize=8)
    ax.set_title(f"Cash Flow — Latest Year ({latest['year']})", fontsize=9)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_buf(fig)


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def draw_header(c, ticker, company_name):
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 28 * mm, PAGE_W, 28 * mm, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, PAGE_H - 15 * mm, company_name[:50])
    c.setFont("Helvetica", 12)
    c.drawString(MARGIN, PAGE_H - 22 * mm, f"Ticker: {ticker}")


def draw_kpi_tiles(c, y_top, kpis: list[tuple[str, str]]):
    """6 tiles, 2 rows of 3. kpis: list of (label, value_str)."""
    tile_w = (PAGE_W - 2 * MARGIN - 2 * 6 * mm) / 3
    tile_h = 18 * mm
    gap = 6 * mm
    for i, (label, value) in enumerate(kpis):
        row, col = divmod(i, 3)
        x = MARGIN + col * (tile_w + gap)
        y = y_top - row * (tile_h + gap) - tile_h
        c.setFillColor(LIGHT_GREY)
        c.roundRect(x, y, tile_w, tile_h, 3, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica", 8)
        c.drawString(x + 4, y + tile_h - 10, label)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x + 4, y + 5, str(value))
    return y_top - 2 * (tile_h + gap)


def draw_capital_allocation_badge(c, x, y, label: str):
    c.setFillColor(GOLD)
    c.roundRect(x, y, 60 * mm, 8 * mm, 3, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + 30 * mm, y + 2.5 * mm, f"Capital Allocation: {label}")


def build_page_1(c, data):
    ticker, company = data["ticker"], data["company"]
    draw_header(c, ticker, company["company_name"])

    ratios = data["ratios"]
    latest = ratios.iloc[-1] if len(ratios) else None

    def fmt(v, suffix=""):
        return f"{v:.1f}{suffix}" if v is not None and pd.notna(v) else "N/A"

    kpis = [
        ("ROE", fmt(latest["return_on_equity_pct"], "%") if latest is not None else "N/A"),
        ("ROCE", fmt(latest["return_on_capital_employed_pct"], "%") if latest is not None else "N/A"),
        ("Net Profit Margin", fmt(latest["net_profit_margin_pct"], "%") if latest is not None else "N/A"),
        ("Debt/Equity", fmt(latest["debt_to_equity"]) if latest is not None else "N/A"),
        ("Revenue CAGR 5yr", fmt(latest["revenue_cagr_5yr"], "%") if latest is not None else "N/A"),
        ("Free Cash Flow", fmt(latest["free_cash_flow_cr"], " Cr") if latest is not None else "N/A"),
    ]
    y_after_tiles = draw_kpi_tiles(c, PAGE_H - 34 * mm, kpis)

    chart_y = y_after_tiles - 65 * mm
    if len(data["pl"]) >= 2:
        buf1 = chart_revenue_profit(data["pl"])
        c.drawImage(_image_reader(buf1), MARGIN, chart_y, width=85 * mm, height=48 * mm, preserveAspectRatio=True)
    if len(ratios) >= 2:
        buf2 = chart_roe_roce(ratios)
        c.drawImage(_image_reader(buf2), MARGIN + 90 * mm, chart_y, width=85 * mm, height=48 * mm, preserveAspectRatio=True)

    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#666666"))
    c.drawString(MARGIN, 10 * mm, f"{company['company_name']} ({ticker}) — Page 1 of 2 — All figures in Rs. Crore unless stated")


def build_page_2(c, data):
    ticker, company = data["ticker"], data["company"]
    draw_header(c, ticker, company["company_name"])

    y = PAGE_H - 34 * mm
    if len(data["bs"]) >= 2:
        valid_years = set(data["pl"]["year"])
        buf1 = chart_bs_composition(data["bs"], valid_years)
        c.drawImage(_image_reader(buf1), MARGIN, y - 50 * mm, width=180 * mm, height=52 * mm, preserveAspectRatio=True)
    y -= 58 * mm

    if len(data["cf"]) >= 1:
        buf2 = chart_cashflow_waterfall(data["cf"])
        if buf2:
            c.drawImage(_image_reader(buf2), MARGIN, y - 50 * mm, width=180 * mm, height=52 * mm, preserveAspectRatio=True)
    y -= 58 * mm

    ratios = data["ratios"]
    latest = ratios.iloc[-1] if len(ratios) else None
    if latest is not None and latest.get("capital_allocation_label"):
        draw_capital_allocation_badge(c, MARGIN, y - 10 * mm, latest["capital_allocation_label"])
    y -= 16 * mm

    pros_cons = data["pros_cons"]
    pros = pros_cons[pros_cons["type"] == "pro"]["text"].tolist() if pros_cons is not None else []
    cons = pros_cons[pros_cons["type"] == "con"]["text"].tolist() if pros_cons is not None else []

    col_w = (PAGE_W - 2 * MARGIN - 6 * mm) / 2
    pro_rows = [[Paragraph(f"&#9679; {t}", pro_style)] for t in pros[:6]] or [[Paragraph("No pros identified.", wrap_style)]]
    con_rows = [[Paragraph(f"&#9679; {t}", con_style)] for t in cons[:6]] or [[Paragraph("No cons identified.", wrap_style)]]

    pro_table = Table(pro_rows, colWidths=[col_w])
    pro_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    con_table = Table(con_rows, colWidths=[col_w])
    con_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GREEN)
    c.drawString(MARGIN, y, "Pros")
    c.setFillColor(RED)
    c.drawString(MARGIN + col_w + 6 * mm, y, "Cons")
    y -= 5 * mm

    pw, ph = pro_table.wrap(col_w, 60 * mm)
    pro_table.drawOn(c, MARGIN, y - ph)
    cw, ch = con_table.wrap(col_w, 60 * mm)
    con_table.drawOn(c, MARGIN + col_w + 6 * mm, y - ch)

    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor("#666666"))
    c.drawString(MARGIN, 10 * mm, f"{company['company_name']} ({ticker}) — Page 2 of 2 — All figures in Rs. Crore unless stated")


def _image_reader(buf):
    from reportlab.lib.utils import ImageReader
    return ImageReader(buf)


def generate_tearsheet(ticker: str, conn=None) -> tuple[bool, str]:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    data = load_tearsheet_data(conn, ticker)
    if data is None:
        if own_conn:
            conn.close()
        return False, "Ticker not found in companies table"

    if len(data["ratios"]) < 3:
        if own_conn:
            conn.close()
        return False, f"Only {len(data['ratios'])} years of data (minimum 3 required)"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{ticker}_tearsheet.pdf"
    c = canvas.Canvas(str(out_path), pagesize=A4)
    build_page_1(c, data)
    c.showPage()
    build_page_2(c, data)
    c.showPage()
    c.save()

    if own_conn:
        conn.close()
    return True, str(out_path)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    test_tickers = ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"]
    for t in test_tickers:
        ok, msg = generate_tearsheet(t, conn)
        size_kb = Path(msg).stat().st_size / 1024 if ok else 0
        print(f"{t}: {'OK' if ok else 'SKIPPED'} - {msg}" + (f" ({size_kb:.0f} KB)" if ok else ""))
    conn.close()