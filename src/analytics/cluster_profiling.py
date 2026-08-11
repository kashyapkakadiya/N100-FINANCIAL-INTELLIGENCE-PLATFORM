"""
src/analytics/cluster_profiling.py — Module 10, Day 37: Cluster Profiling,
Correlation Heatmap, Outlier Detection, Portfolio Statistics.
"""
from __future__ import annotations
import sys
import sqlite3
from pathlib import Path

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"

CORRELATION_KPIS = [
    "return_on_equity_pct", "return_on_capital_employed_pct", "net_profit_margin_pct",
    "debt_to_equity", "interest_coverage", "asset_turnover", "free_cash_flow_cr",
    "revenue_cagr_5yr", "pat_cagr_5yr", "eps_cagr_5yr",
]
KPI_LABELS = {
    "return_on_equity_pct": "ROE", "return_on_capital_employed_pct": "ROCE",
    "net_profit_margin_pct": "NPM", "debt_to_equity": "D/E",
    "interest_coverage": "ICR", "asset_turnover": "Asset Turnover",
    "free_cash_flow_cr": "FCF", "revenue_cagr_5yr": "Rev CAGR 5yr",
    "pat_cagr_5yr": "PAT CAGR 5yr", "eps_cagr_5yr": "EPS CAGR 5yr",
}


def load_latest_ratios(conn) -> pd.DataFrame:
    return pd.read_sql("""
        SELECT f1.*, s.broad_sector FROM financial_ratios f1
        LEFT JOIN sectors s ON f1.company_id = s.company_id
        WHERE f1.net_profit_margin_pct IS NOT NULL
        AND f1.year = (SELECT MAX(year) FROM financial_ratios f2
                       WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)


def build_correlation_heatmap(df: pd.DataFrame):
    """
    Raw Pearson correlation, per spec - no winsorization applied here
    (unlike clustering, where outlier-domination actively broke cluster
    assignment; a correlation matrix's job is arguably to show true
    relationships including outlier influence). BUT: verified during
    testing that ROE<->Asset Turnover shows 0.96 with all 92 companies,
    dropping to 0.57 once the 8 companies already flagged in
    outlier_report.csv are excluded - nearly half the apparent correlation
    strength is a few extreme points, not a broad-based relationship.
    Flagged directly on the chart so this isn't lost if the PNG is viewed
    without this context.
    """
    corr_df = df[CORRELATION_KPIS].rename(columns=KPI_LABELS)
    corr_matrix = corr_df.corr(method="pearson")

    fig, ax = plt.subplots(figsize=(9, 8))
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="RdBu_r", center=0,
                vmin=-1, vmax=1, square=True, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title("Pearson Correlation — 10 Core KPIs (Latest Year, All 92 Companies)", fontsize=11)
    fig.text(0.5, 0.01,
              "Caution: raw correlation, sensitive to outliers - e.g. ROE\u2194Asset Turnover drops from 0.96 to 0.57\n"
              "once companies in outlier_report.csv are excluded. See sprint6 notes before over-interpreting strength.",
              ha="center", fontsize=7.5, color="#666666")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORTS_DIR / "correlation_heatmap.png", dpi=150)
    plt.close(fig)
    return corr_matrix


def detect_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score per metric, computed WITHIN each broad_sector (not pooled
    across the whole universe) - a company's D/E of 6 is normal for a bank
    but extreme for an IT company, so sector-relative Z-scores are the only
    meaningful way to flag this, consistent with every sector-relative
    convention already established in this project (D/E carve-out,
    valuation flags, etc)."""
    rows = []
    for sector, group in df.groupby("broad_sector"):
        for metric in CORRELATION_KPIS:
            values = group[metric]
            mean, std = values.mean(), values.std()
            if pd.isna(std) or std == 0:
                continue
            z_scores = (values - mean) / std
            outliers = group[z_scores.abs() > 3]
            for idx in outliers.index:
                rows.append({
                    "company_id": df.loc[idx, "company_id"],
                    "metric": metric,
                    "value": df.loc[idx, metric],
                    "z_score": round(z_scores.loc[idx], 2),
                    "sector": sector,
                    "sector_mean": round(mean, 2),
                    "sector_std": round(std, 2),
                })
    return pd.DataFrame(rows)


def build_portfolio_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for metric in CORRELATION_KPIS:
        values = df[metric].dropna()
        rows.append({
            "metric": metric,
            "P10": round(values.quantile(0.10), 2),
            "P25": round(values.quantile(0.25), 2),
            "P50": round(values.quantile(0.50), 2),
            "P75": round(values.quantile(0.75), 2),
            "P90": round(values.quantile(0.90), 2),
            "Mean": round(values.mean(), 2),
            "Std": round(values.std(), 2),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    df = load_latest_ratios(conn)
    conn.close()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corr_matrix = build_correlation_heatmap(df)
    print("correlation_heatmap.png saved")
    print()

    outliers_df = detect_outliers(df)
    outliers_df.to_csv(OUTPUT_DIR / "outlier_report.csv", index=False)
    print(f"outlier_report.csv: {len(outliers_df)} outlier flags ({outliers_df['company_id'].nunique()} companies)")
    if len(outliers_df):
        print(outliers_df.sort_values("z_score", key=abs, ascending=False).head(10).to_string(index=False))
    print()

    stats_df = build_portfolio_stats(df)
    stats_df.to_csv(OUTPUT_DIR / "portfolio_stats.csv", index=False)
    print("portfolio_stats.csv:")
    print(stats_df.to_string(index=False))