"""
src/analytics/valuation.py — Module 6, Day 26: Valuation & Market Data.

FCF Yield = FCF / market_cap_crore x 100.
5yr median P/E computed from all available years in market_cap (2019-2024,
so effectively a 6yr window where 6 years exist - documented, not literally
forced to exactly 5).
Overvaluation flag compares LATEST year P/E against the CURRENT sector
median P/E (not the company's own 5yr median) - "sector_median x 1.5/0.7"
per the spec's exact wording in Module 6 / Section 13.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def compute_valuation_summary(conn=None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    mc = pd.read_sql("SELECT * FROM market_cap", conn)
    companies = pd.read_sql("SELECT id, company_name FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)

    # Latest-year valuation snapshot per company
    latest = mc.sort_values("cal_year").groupby("company_id").tail(1).copy()

    # FCF (latest year with real P&L data) - reuse the same "latest year"
    # discipline as everywhere else in this project (not a bare MAX(year))
    fcf = pd.read_sql("""
        SELECT company_id, free_cash_flow_cr FROM financial_ratios f1
        WHERE net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)

    df = latest.merge(fcf, on="company_id", how="left")
    df = df.merge(companies, left_on="company_id", right_on="id", how="left")
    df = df.merge(sectors, on="company_id", how="left")

    df["fcf_yield_pct"] = (df["free_cash_flow_cr"] / df["market_cap_crore"] * 100).where(
        df["market_cap_crore"].notna() & (df["market_cap_crore"] != 0)
    )

    # N-year median P/E per company (all years available in market_cap, 2019-2024)
    median_pe = mc.groupby("company_id")["pe_ratio"].median().rename("median_pe_all_years")
    df = df.merge(median_pe, on="company_id", how="left")

    # Sector median P/E, LATEST year only
    sector_median_pe = df.groupby("broad_sector")["pe_ratio"].median().rename("sector_median_pe")
    df = df.merge(sector_median_pe, on="broad_sector", how="left")

    df["pe_vs_sector_median_pct"] = (
        (df["pe_ratio"] - df["sector_median_pe"]) / df["sector_median_pe"] * 100
    ).where(df["sector_median_pe"].notna() & (df["sector_median_pe"] != 0))

    def flag_row(row):
        if pd.isna(row["pe_ratio"]) or pd.isna(row["sector_median_pe"]) or row["sector_median_pe"] == 0:
            return "Unknown"
        if row["pe_ratio"] > row["sector_median_pe"] * 1.5:
            return "Caution"
        if row["pe_ratio"] < row["sector_median_pe"] * 0.7:
            return "Discount"
        return "Fair"

    df["flag"] = df.apply(flag_row, axis=1)

    result = df[[
        "company_id", "company_name", "broad_sector", "pe_ratio", "pb_ratio", "ev_ebitda",
        "fcf_yield_pct", "median_pe_all_years", "pe_vs_sector_median_pct", "flag",
    ]].rename(columns={
        "broad_sector": "sector", "pe_ratio": "P/E", "pb_ratio": "P/B", "ev_ebitda": "EV/EBITDA",
        "fcf_yield_pct": "FCF_yield_pct", "median_pe_all_years": "5yr_median_PE",
        "pe_vs_sector_median_pct": "PE_vs_sector_median_pct",
    })

    if own_conn:
        conn.close()
    return result


def build_valuation_outputs():
    conn = sqlite3.connect(DB_PATH)
    summary = compute_valuation_summary(conn)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_excel(OUTPUT_DIR / "valuation_summary.xlsx", index=False)

    flagged = summary[summary["flag"].isin(["Caution", "Discount"])].sort_values("P/E", ascending=False)
    flagged.to_csv(OUTPUT_DIR / "valuation_flags.csv", index=False)

    conn.close()
    return summary, flagged


if __name__ == "__main__":
    summary, flagged = build_valuation_outputs()
    print(f"valuation_summary.xlsx: {len(summary)} rows")
    print(summary["flag"].value_counts())
    print(f"\nvaluation_flags.csv: {len(flagged)} rows")
    print(flagged[["company_id", "sector", "P/E", "flag"]].head(10).to_string(index=False))