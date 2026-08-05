"""
src/analytics/build_cashflow_intelligence.py — Module 7, Days 31-32:
Cash Flow Intelligence Report + Capital Allocation Report.

Reuses financial_ratios (Sprint 2) wherever it already has the needed
value per company-year, rather than re-deriving from raw tables:
  - capex_intensity_pct / capex_intensity_label: latest-year row, as-is
  - fcf_conversion_pct: latest-year row, as-is
  - total_debt_cr: used as the borrowings history for the deleveraging check
  - cfo_sign / cff_sign: used for the distress/deleveraging flags directly,
    since sign is all those checks need (the actual CFO/CFF numeric values
    are only pulled from the raw cashflow table for distress_alerts.csv,
    where the spec explicitly wants real numbers, not just signs)
  - capital_allocation_label: latest-year row, as-is

FCF CAGR 5yr is NOT in financial_ratios (Sprint 2 only stored revenue/PAT/
EPS CAGR), so it's computed here fresh using the same compute_cagr_for_window
from cagr.py.

CFO Quality Score here is recomputed as a numeric average (not just the
label Sprint 2 stores), using cfo_quality_score_numeric() from the extended
cashflow_kpis.py.
"""
from __future__ import annotations
import sys
import sqlite3
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.cagr import compute_cagr_for_window
from analytics.cashflow_kpis import cfo_quality_score_numeric, detect_distress_signal, detect_deleveraging

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def build_capital_allocation_csv(conn) -> pd.DataFrame:
    """
    Day 32 Task 1: regenerate capital_allocation.csv (Sprint 2's original
    output wasn't present in this rebuild) - verify complete for all
    company-years using financial_ratios.

    Filtered to net_profit_margin_pct IS NOT NULL - i.e. real annual P&L
    years only. Found during testing: without this filter, the interim
    balance-sheet-only snapshot rows (e.g. '2024-09' alongside the real
    '2024-03' annual close - the same recurring issue first found in
    Sprint 1/SIEMENS and re-triggered in Sprint 2's screener and Sprint 4's
    dashboard) have null CFO/CFI/CFF signs, which .tail(1) or any
    "latest year" logic would pick up as "Unclassified" for ~89% of
    companies - not a real finding, an artifact of including non-P&L rows.
    """
    df = pd.read_sql("""
        SELECT company_id, year, cfo_sign, cfi_sign, cff_sign, capital_allocation_label
        FROM financial_ratios
        WHERE net_profit_margin_pct IS NOT NULL
    """, conn)
    df.to_csv(OUTPUT_DIR / "capital_allocation.csv", index=False)
    return df


def build_pattern_changes_csv(capital_alloc_df: pd.DataFrame) -> pd.DataFrame:
    """Day 32 Task 4: companies whose capital allocation pattern changed
    year-over-year (e.g. Reinvestor -> Distress Signal)."""
    rows = []
    for cid, g in capital_alloc_df.sort_values("year").groupby("company_id"):
        labels = g["capital_allocation_label"].tolist()
        years = g["year"].tolist()
        for i in range(1, len(labels)):
            if labels[i] != labels[i - 1]:
                rows.append({
                    "company_id": cid,
                    "from_year": years[i - 1], "to_year": years[i],
                    "from_pattern": labels[i - 1], "to_pattern": labels[i],
                })
    changes_df = pd.DataFrame(rows)
    changes_df.to_csv(OUTPUT_DIR / "pattern_changes.csv", index=False)
    return changes_df


def build_cashflow_intelligence(conn) -> pd.DataFrame:
    ratios = pd.read_sql("""
        SELECT f.*, s.broad_sector FROM financial_ratios f
        LEFT JOIN sectors s ON f.company_id = s.company_id
    """, conn)
    pl = pd.read_sql("SELECT company_id, year, net_profit FROM profitandloss", conn)
    cf = pd.read_sql("SELECT company_id, year, operating_activity, financing_activity FROM cashflow", conn)

    companies = pd.read_sql("SELECT id FROM companies", conn)["id"].tolist()
    rows = []

    for cid in companies:
        company_ratios = ratios[ratios["company_id"] == cid].sort_values("year")
        real_rows = company_ratios[company_ratios["net_profit_margin_pct"].notna()]
        if real_rows.empty:
            continue
        latest = real_rows.iloc[-1]
        sector = latest["broad_sector"]

        # CFO Quality Score - numeric average over up to 5yr, from raw CFO + PAT
        company_cf = cf[cf["company_id"] == cid].sort_values("year").tail(5)
        company_pl = pl[pl["company_id"] == cid].sort_values("year")
        merged = company_cf.merge(company_pl, on=["company_id", "year"], how="inner")
        cfo_score, cfo_label = cfo_quality_score_numeric(
            merged["operating_activity"].tolist(), merged["net_profit"].tolist()
        )

        # FCF CAGR 5yr - computed fresh (not stored in financial_ratios)
        fcf_series = real_rows.set_index("year")["free_cash_flow_cr"].dropna().to_dict()
        fcf_cagr, fcf_cagr_flag = compute_cagr_for_window(fcf_series, 5)

        # Distress / deleveraging flags - via signs already in financial_ratios
        distress_flag = latest["cfo_sign"] == "-" and latest["cff_sign"] == "+"
        borrowings_series = real_rows["total_debt_cr"]
        deleveraging_flag = latest["cff_sign"] == "-" and (
            borrowings_series.dropna().iloc[-1] < borrowings_series.dropna().iloc[-2]
            if len(borrowings_series.dropna()) >= 2 else False
        )

        rows.append({
            "company_id": cid,
            "sector": sector,
            "cfo_quality_score": cfo_score,
            "cfo_quality_label": cfo_label,
            "capex_intensity_pct": latest["capex_intensity_pct"],
            "capex_label": latest["capex_intensity_label"],
            "fcf_cagr_5yr": round(fcf_cagr, 2) if fcf_cagr is not None else None,
            "fcf_cagr_5yr_flag": fcf_cagr_flag,
            "fcf_conversion_pct": latest["fcf_conversion_pct"],
            "distress_flag": distress_flag,
            "deleveraging_flag": deleveraging_flag,
            "capital_allocation_label": latest["capital_allocation_label"],
        })

    result_df = pd.DataFrame(rows)
    result_df.to_excel(OUTPUT_DIR / "cashflow_intelligence.xlsx", index=False)

    # distress_alerts.csv - include actual CFO/CFF values + latest net profit
    distress = result_df[result_df["distress_flag"]].copy()
    alert_rows = []
    for _, row in distress.iterrows():
        cid = row["company_id"]
        latest_year = ratios[(ratios["company_id"] == cid) & (ratios["net_profit_margin_pct"].notna())]["year"].max()
        cf_row = cf[(cf["company_id"] == cid) & (cf["year"] == latest_year)]
        pl_row = pl[(pl["company_id"] == cid) & (pl["year"] == latest_year)]
        alert_rows.append({
            "company_id": cid,
            "year": latest_year,
            "cfo_cr": cf_row["operating_activity"].iloc[0] if len(cf_row) else None,
            "cff_cr": cf_row["financing_activity"].iloc[0] if len(cf_row) else None,
            "latest_net_profit_cr": pl_row["net_profit"].iloc[0] if len(pl_row) else None,
        })
    alerts_df = pd.DataFrame(alert_rows)
    alerts_df.to_csv(OUTPUT_DIR / "distress_alerts.csv", index=False)

    return result_df, alerts_df


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    capital_alloc_df = build_capital_allocation_csv(conn)
    print(f"capital_allocation.csv: {len(capital_alloc_df)} rows, {capital_alloc_df['company_id'].nunique()} companies")

    changes_df = build_pattern_changes_csv(capital_alloc_df)
    print(f"pattern_changes.csv: {len(changes_df)} year-over-year pattern changes")

    print()
    print("Latest-year distribution across the 8 patterns:")
    latest_per_company = capital_alloc_df.sort_values("year").groupby("company_id").tail(1)
    print(latest_per_company["capital_allocation_label"].value_counts())

    print()
    result_df, alerts_df = build_cashflow_intelligence(conn)
    print(f"cashflow_intelligence.xlsx: {len(result_df)} rows, {len(result_df.columns)} columns")
    print(result_df["cfo_quality_label"].value_counts())
    print(result_df["capex_label"].value_counts())
    print()
    print(f"distress_alerts.csv: {len(alerts_df)} companies flagged")
    if len(alerts_df):
        print(alerts_df.to_string(index=False))
    print(f"\nDeleveraging companies: {result_df['deleveraging_flag'].sum()}")

    conn.close()