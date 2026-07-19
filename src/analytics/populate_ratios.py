"""
populate_ratios.py — Module 2, Day 12: runs the full Ratio Engine across
all 92 companies and every available year, writes the financial_ratios table.

Design decisions (documented for the Sprint 2 retro / edge case log):
- Row universe = UNION of (company_id, year) pairs from profitandloss and
  balancesheet (not intersection). This maximises coverage - companies with
  P&L but a missing BS year (or vice versa) still get a row, just with the
  BS-dependent ratios as None rather than being dropped entirely.
- Cash flow is LEFT-joined on top of that. Companies with known CF gaps
  (LODHA, HAL, IRFC - see Sprint 1 retro) get None for CFO/FCF-dependent
  ratios in the years they're missing, not a crash or a dropped row.
- CAGR windows are computed per company using that company's full P&L/EPS
  history, attached to the row for the LATEST P&L year present (not the
  latest row overall - see the "latest year" bug note below).
- composite_quality_score here is a pragmatic first pass (winsorized P10/P90
  across all company-year rows) so the column isn't empty. Module 5 (Health
  Scoring, later sprint) is expected to build the authoritative version.

IMPORTANT - "latest year" bug found and fixed during Day 12 testing:
Balance sheet has an extra interim snapshot for most March-ending companies
(e.g. TCS has a real annual row at '2024-03' AND a leftover row at '2024-09'
with no matching P&L). A naive MAX(year) picks '2024-09', which has no P&L
data, silently nulling out ROE/margins/CAGR for that "latest" row. This
broke the Day 14 screener test (returned 1 company instead of 15-50) until
fixed. get_latest_pl_year() below is the reusable, correct version - use
it anywhere "latest year per company" is needed (screener, dashboard, etc).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.ratios import (
    net_profit_margin, operating_profit_margin, opm_cross_check,
    return_on_equity, return_on_capital_employed, return_on_assets,
    debt_to_equity, high_leverage_flag, interest_coverage, icr_risk_flag,
    net_debt, asset_turnover,
)
from analytics.cagr import compute_cagr_for_window
from analytics.cashflow_kpis import (
    free_cash_flow, capex_intensity, fcf_conversion_rate,
    classify_capital_allocation,
)

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"


def load_source_tables(conn):
    pl = pd.read_sql("SELECT * FROM profitandloss", conn)
    bs = pd.read_sql("SELECT * FROM balancesheet", conn)
    cf = pd.read_sql("SELECT * FROM cashflow", conn)
    companies = pd.read_sql("SELECT id, face_value FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    return pl, bs, cf, companies, sectors


def build_row_universe(pl, bs):
    """Union of (company_id, year) from P&L and BS."""
    keys_pl = pl[["company_id", "year"]]
    keys_bs = bs[["company_id", "year"]]
    return pd.concat([keys_pl, keys_bs]).drop_duplicates().reset_index(drop=True)


def get_latest_pl_year(pl_by_company: dict, company_id: str):
    """
    Correct 'latest year' for a company: the latest year with an actual P&L
    row (sales not null) - NOT just the latest row in any joined table.
    Reuse this everywhere 'latest year' is needed downstream.
    """
    if company_id not in pl_by_company:
        return None
    hist = pl_by_company[company_id]
    valid_years = hist[hist["sales"].notna()].index
    return valid_years.max() if len(valid_years) else None


def compute_all_ratios():
    conn = sqlite3.connect(DB_PATH)
    pl, bs, cf, companies, sectors = load_source_tables(conn)

    universe = build_row_universe(pl, bs)
    merged = universe.merge(pl, on=["company_id", "year"], how="left", suffixes=("", "_pl"))
    merged = merged.merge(bs, on=["company_id", "year"], how="left", suffixes=("", "_bs"))
    merged = merged.merge(cf, on=["company_id", "year"], how="left", suffixes=("", "_cf"))
    merged = merged.merge(companies, left_on="company_id", right_on="id", how="left")
    merged = merged.merge(sectors, on="company_id", how="left")

    pl_by_company = {cid: g.set_index("year") for cid, g in pl.groupby("company_id")}

    rows = []
    for _, r in merged.iterrows():
        sales, net_profit = r.get("sales"), r.get("net_profit")
        operating_profit, depreciation = r.get("operating_profit"), r.get("depreciation")
        other_income, interest = r.get("other_income"), r.get("interest")
        equity_capital, reserves = r.get("equity_capital"), r.get("reserves")
        borrowings, investments = r.get("borrowings"), r.get("investments")
        total_assets = r.get("total_assets")
        opex_activity, invest_activity = r.get("operating_activity"), r.get("investing_activity")
        broad_sector = r.get("broad_sector")
        face_value = r.get("face_value")
        eps = r.get("eps")
        dividend_payout = r.get("dividend_payout")

        npm = net_profit_margin(sales, net_profit) if pd.notna(sales) and pd.notna(net_profit) else None
        opm_computed = operating_profit_margin(sales, operating_profit) if pd.notna(sales) and pd.notna(operating_profit) else None
        opm_diff = opm_cross_check(opm_computed, r.get("opm_percentage"))
        opm_flag = bool(opm_diff is not None and opm_diff > 1.0)

        roe = (return_on_equity(net_profit, equity_capital, reserves)
               if pd.notna(net_profit) and pd.notna(equity_capital) and pd.notna(reserves) else None)
        roce = (return_on_capital_employed(operating_profit, depreciation, equity_capital, reserves, borrowings)
                if pd.notna(operating_profit) and pd.notna(equity_capital) and pd.notna(reserves) and pd.notna(borrowings) else None)
        roa = return_on_assets(net_profit, total_assets) if pd.notna(net_profit) and pd.notna(total_assets) else None

        de = debt_to_equity(borrowings, equity_capital, reserves) if pd.notna(equity_capital) and pd.notna(reserves) else None
        lev_flag = high_leverage_flag(de, broad_sector)
        icr_val, icr_label = (interest_coverage(operating_profit, other_income, interest)
                               if pd.notna(operating_profit) and pd.notna(interest) else (None, None))
        icr_flag = icr_risk_flag(icr_val)
        ndebt = net_debt(borrowings, investments) if pd.notna(borrowings) or pd.notna(investments) else None
        at = asset_turnover(sales, total_assets) if pd.notna(sales) and pd.notna(total_assets) else None

        fcf = (free_cash_flow(opex_activity, invest_activity)
               if pd.notna(opex_activity) and pd.notna(invest_activity) else None)
        capex_cr = abs(invest_activity) if pd.notna(invest_activity) else None
        capex_result = (capex_intensity(invest_activity, sales)
                         if pd.notna(invest_activity) and pd.notna(sales) else None)
        capex_pct = capex_result["value"] if capex_result else None
        capex_label = capex_result["label"] if capex_result else None
        fcf_conv = fcf_conversion_rate(fcf, operating_profit) if fcf is not None and pd.notna(operating_profit) else None

        cfo_pat_ratio = (opex_activity / net_profit) if pd.notna(opex_activity) and pd.notna(net_profit) and net_profit != 0 else None
        cap_alloc = classify_capital_allocation(opex_activity, invest_activity, r.get("financing_activity"), cfo_pat_ratio)

        bvps = None
        if pd.notna(equity_capital) and pd.notna(reserves) and pd.notna(face_value) and face_value not in (0, None):
            shares = equity_capital / face_value
            if shares > 0:
                bvps = (equity_capital + reserves) / shares

        cid = r["company_id"]
        rev_cagr, rev_flag, pat_cagr, pat_flag, eps_cagr, eps_flag = (None,) * 6
        if cid in pl_by_company:
            latest_pl_year = get_latest_pl_year(pl_by_company, cid)
            if latest_pl_year is not None and r["year"] == latest_pl_year:
                hist = pl_by_company[cid]
                sales_series = hist["sales"].dropna().to_dict()
                pat_series = hist["net_profit"].dropna().to_dict()
                eps_series = hist["eps"].dropna().to_dict()
                rev_cagr, rev_flag = compute_cagr_for_window(sales_series, 5)
                pat_cagr, pat_flag = compute_cagr_for_window(pat_series, 5)
                eps_cagr, eps_flag = compute_cagr_for_window(eps_series, 5)

        rows.append({
            "company_id": cid, "year": r["year"],
            "net_profit_margin_pct": npm,
            "operating_profit_margin_pct": opm_computed,
            "opm_cross_check_flag": opm_flag,
            "return_on_equity_pct": roe,
            "return_on_capital_employed_pct": roce,
            "return_on_assets_pct": roa,
            "debt_to_equity": de,
            "high_leverage_flag": lev_flag,
            "interest_coverage": icr_val,
            "icr_label": icr_label,
            "icr_risk_flag": icr_flag,
            "asset_turnover": at,
            "net_debt_cr": ndebt,
            "free_cash_flow_cr": fcf,
            "capex_cr": capex_cr,
            "capex_intensity_pct": capex_pct,
            "capex_intensity_label": capex_label,
            "fcf_conversion_pct": fcf_conv,
            "cfo_sign": cap_alloc["cfo_sign"], "cfi_sign": cap_alloc["cfi_sign"],
            "cff_sign": cap_alloc["cff_sign"], "capital_allocation_label": cap_alloc["pattern_label"],
            "earnings_per_share": eps,
            "book_value_per_share": bvps,
            "dividend_payout_ratio_pct": dividend_payout,
            "total_debt_cr": borrowings,
            "cash_from_operations_cr": opex_activity,
            "revenue_cagr_5yr": rev_cagr, "revenue_cagr_5yr_flag": rev_flag,
            "pat_cagr_5yr": pat_cagr, "pat_cagr_5yr_flag": pat_flag,
            "eps_cagr_5yr": eps_cagr, "eps_cagr_5yr_flag": eps_flag,
        })

    result = pd.DataFrame(rows)

    def winsorize_score(series):
        s = series.dropna()
        if len(s) < 2:
            return pd.Series(50.0, index=series.index)
        p10, p90 = np.percentile(s, 10), np.percentile(s, 90)
        clipped = series.clip(lower=p10, upper=p90)
        scaled = (clipped - p10) / (p90 - p10) * 100 if p90 != p10 else pd.Series(50.0, index=series.index)
        return scaled

    roe_score = winsorize_score(result["return_on_equity_pct"])
    roce_score = winsorize_score(result["return_on_capital_employed_pct"])
    fcf_score = winsorize_score(result["free_cash_flow_cr"])
    de_score = winsorize_score(-result["debt_to_equity"].fillna(result["debt_to_equity"].median()))

    result["composite_quality_score"] = (
        0.30 * roe_score.fillna(0) + 0.25 * fcf_score.fillna(0)
        + 0.25 * roce_score.fillna(0) + 0.20 * de_score.fillna(0)
    ).round(1)

    conn.close()
    return result


def write_to_db(df: pd.DataFrame):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS financial_ratios")
    conn.execute("""
        CREATE TABLE financial_ratios (
            company_id TEXT NOT NULL, year TEXT NOT NULL,
            net_profit_margin_pct REAL, operating_profit_margin_pct REAL,
            opm_cross_check_flag INTEGER,
            return_on_equity_pct REAL, return_on_capital_employed_pct REAL, return_on_assets_pct REAL,
            debt_to_equity REAL, high_leverage_flag INTEGER,
            interest_coverage REAL, icr_label TEXT, icr_risk_flag INTEGER,
            asset_turnover REAL, net_debt_cr REAL,
            free_cash_flow_cr REAL, capex_cr REAL,
            capex_intensity_pct REAL, capex_intensity_label TEXT, fcf_conversion_pct REAL,
            cfo_sign TEXT, cfi_sign TEXT, cff_sign TEXT, capital_allocation_label TEXT,
            earnings_per_share REAL, book_value_per_share REAL, dividend_payout_ratio_pct REAL,
            total_debt_cr REAL, cash_from_operations_cr REAL,
            revenue_cagr_5yr REAL, revenue_cagr_5yr_flag TEXT,
            pat_cagr_5yr REAL, pat_cagr_5yr_flag TEXT,
            eps_cagr_5yr REAL, eps_cagr_5yr_flag TEXT,
            composite_quality_score REAL,
            PRIMARY KEY (company_id, year),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)
    df.to_sql("financial_ratios", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    result = compute_all_ratios()
    write_to_db(result)
    print(f"financial_ratios populated: {len(result)} rows")
    print(f"Columns: {len(result.columns)}")
    print(result[["company_id", "year", "net_profit_margin_pct", "return_on_equity_pct",
                   "debt_to_equity", "composite_quality_score"]].head(10).to_string())