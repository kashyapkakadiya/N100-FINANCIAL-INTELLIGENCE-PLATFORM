"""
src/analytics/composite_score.py — Module 2/3, Day 17: Composite Quality Score

Weights per project spec (Section 25.1):
  35% Profitability = ROE(15%) + ROCE(10%) + NPM(10%)
  30% Cash Quality  = FCF CAGR 5yr(15%) + CFO/PAT ratio(10%) + FCF positive flag(5%)
  20% Growth        = Revenue CAGR 5yr(10%) + PAT CAGR 5yr(10%)
  15% Leverage      = D/E score(10%) + ICR score(5%)

Each metric is winsorized at P10/P90 then scaled to 0-100 before weighting.
Two versions are computed:
  - composite_quality_score_universe: winsorized against the full 92-company pool
  - composite_quality_score_sector: winsorized within each company's own
    broad_sector (so an IT company is compared to other IT companies, not
    diluted against banks/utilities with structurally different profiles)
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.cagr import compute_cagr_for_window

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"


def _winsorize_0_100(series: pd.Series, invert: bool = False) -> pd.Series:
    """Cap at P10/P90, scale to 0-100. invert=True means lower raw value = higher score (e.g. D/E)."""
    s = series.dropna()
    if len(s) < 2:
        return pd.Series(50.0, index=series.index)
    p10, p90 = np.percentile(s, 10), np.percentile(s, 90)
    if p90 == p10:
        return pd.Series(50.0, index=series.index)
    clipped = series.clip(lower=p10, upper=p90)
    scaled = (clipped - p10) / (p90 - p10) * 100
    return (100 - scaled) if invert else scaled


def compute_fcf_cagr_and_cfo_pat(conn) -> pd.DataFrame:
    """
    Per-company: FCF 5yr CAGR + average CFO/PAT ratio over available years
    (up to 5). Computed from raw cashflow/profitandloss since Sprint 2's
    financial_ratios table only stores the FCF *value*, not its CAGR, and
    only stores a CFO-quality *label*, not the numeric ratio.
    """
    cf = pd.read_sql("SELECT company_id, year, operating_activity, investing_activity FROM cashflow", conn)
    pl = pd.read_sql("SELECT company_id, year, net_profit FROM profitandloss", conn)
    cf["fcf"] = cf["operating_activity"] + cf["investing_activity"]

    rows = []
    for cid, g in cf.groupby("company_id"):
        fcf_series = g.set_index("year")["fcf"].dropna().to_dict()
        fcf_cagr, fcf_flag = compute_cagr_for_window(fcf_series, 5)

        merged = g.merge(pl[pl["company_id"] == cid], on=["company_id", "year"], how="inner")
        merged = merged.sort_values("year").tail(5)
        merged = merged[merged["net_profit"] != 0]
        cfo_pat_ratio = (merged["operating_activity"] / merged["net_profit"]).mean() if len(merged) else None

        rows.append({"company_id": cid, "fcf_cagr_5yr": fcf_cagr, "cfo_pat_ratio_avg": cfo_pat_ratio})
    return pd.DataFrame(rows)


def compute_composite_scores(universe: pd.DataFrame, conn=None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    extra = compute_fcf_cagr_and_cfo_pat(conn)
    df = universe.merge(extra, on="company_id", how="left")

    df["fcf_positive_flag"] = (df["free_cash_flow_cr"] > 0).astype(int) * 100

    debt_free_mask = df["icr_label"] == "Debt Free"

    def score_pool(pool: pd.DataFrame) -> pd.DataFrame:
        roe_s = _winsorize_0_100(pool["return_on_equity_pct"])
        roce_s = _winsorize_0_100(pool["return_on_capital_employed_pct"])
        npm_s = _winsorize_0_100(pool["net_profit_margin_pct"])
        fcf_cagr_s = _winsorize_0_100(pool["fcf_cagr_5yr"])
        cfo_pat_s = _winsorize_0_100(pool["cfo_pat_ratio_avg"])
        fcf_flag_s = pool["fcf_positive_flag"]
        rev_cagr_s = _winsorize_0_100(pool["revenue_cagr_5yr"])
        pat_cagr_s = _winsorize_0_100(pool["pat_cagr_5yr"])
        de_s = _winsorize_0_100(pool["debt_to_equity"], invert=True)
        icr_s = _winsorize_0_100(pool["interest_coverage"])
        icr_s = icr_s.where(~debt_free_mask.loc[pool.index], 100.0)

        profitability = 0.15 * roe_s.fillna(0) + 0.10 * roce_s.fillna(0) + 0.10 * npm_s.fillna(0)
        cash_quality = 0.15 * fcf_cagr_s.fillna(0) + 0.10 * cfo_pat_s.fillna(0) + 0.05 * fcf_flag_s.fillna(0)
        growth = 0.10 * rev_cagr_s.fillna(0) + 0.10 * pat_cagr_s.fillna(0)
        leverage = 0.10 * de_s.fillna(0) + 0.05 * icr_s.fillna(0)

        return (profitability + cash_quality + growth + leverage).round(1)

    df["composite_quality_score_universe"] = score_pool(df)

    sector_scores = pd.Series(index=df.index, dtype=float)
    for sector, group in df.groupby("broad_sector"):
        sector_scores.loc[group.index] = score_pool(group)
    df["composite_quality_score_sector"] = sector_scores

    if own_conn:
        conn.close()
    return df


if __name__ == "__main__":
    from screener.engine import build_universe

    conn = sqlite3.connect(DB_PATH)
    universe = build_universe(conn)
    scored = compute_composite_scores(universe, conn)
    print(scored[["company_id", "broad_sector", "composite_quality_score_universe",
                  "composite_quality_score_sector"]].sort_values(
        "composite_quality_score_universe", ascending=False).head(10).to_string(index=False))
    conn.close()