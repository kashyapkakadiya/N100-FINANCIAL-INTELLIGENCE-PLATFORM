"""
src/analytics/peer.py — Module 4, Day 18: Peer Percentile Rankings

Computes PERCENT_RANK for 10 metrics within each of 11 peer groups.
D/E is inverted (lower D/E = higher percentile, since less debt is "better").
ICR: a "Debt Free" company is treated as the best possible ICR (percentile 1.0),
consistent with how Debt Free is handled everywhere else in this pipeline
(screener's min_icr filter, composite score).

Companies not in any peer group (36 of 92, per Sprint 1's coverage matrix)
are NOT an error - build_peer_percentiles() simply produces no rows for
them, and get_company_peer_status() below returns a clear "No peer group
assigned" message for that specific lookup case (Module 5/dashboard use).
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screener.engine import build_universe

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"

# metric_name -> invert_percentile
METRICS = {
    "return_on_equity_pct":            False,
    "return_on_capital_employed_pct":  False,
    "net_profit_margin_pct":           False,
    "debt_to_equity":                  True,   # lower D/E = better = higher percentile
    "free_cash_flow_cr":               False,
    "pat_cagr_5yr":                    False,
    "revenue_cagr_5yr":                False,
    "eps_cagr_5yr":                    False,
    "interest_coverage":               False,
    "asset_turnover":                  False,
}


def _percent_rank(series: pd.Series) -> pd.Series:
    """
    SQL-standard PERCENT_RANK(): (rank - 1) / (n - 1), spanning exactly
    0.0 to 1.0. NOT the same as pandas' .rank(pct=True), which spans
    1/n to 1.0 and never reaches 0 - using that instead would mean the
    best company in a group never actually shows a 100th-percentile D/E
    even when it has the lowest debt in the group (caught during Day 18
    testing: HCLTECH, lowest D/E in IT Services, showed 0.8 not 1.0).
    A single-company group returns 1.0 (nothing to rank against).
    """
    n = series.notna().sum()
    if n <= 1:
        return pd.Series([1.0 if pd.notna(v) else None for v in series], index=series.index)
    ranks = series.rank(method="min", ascending=True)
    return (ranks - 1) / (n - 1)


def build_peer_percentiles(conn=None) -> pd.DataFrame:
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    universe = build_universe(conn)
    peer_groups = pd.read_sql("SELECT peer_group_name, company_id FROM peer_groups", conn)

    merged = peer_groups.merge(universe, on="company_id", how="inner")

    rows = []
    for group_name, group_df in merged.groupby("peer_group_name"):
        for metric, invert in METRICS.items():
            values = group_df[metric].copy()

            if metric == "interest_coverage":
                # Debt Free -> treat as the best (infinite) ICR: give it the
                # max numeric value in the group before ranking, so it lands
                # at percentile 1.0 rather than being dropped as NaN.
                debt_free_mask = group_df["icr_label"] == "Debt Free"
                if debt_free_mask.any() and values.notna().any():
                    values = values.copy()
                    values.loc[debt_free_mask] = values.max() + 1
                elif debt_free_mask.any():
                    values.loc[debt_free_mask] = 1  # only debt-free companies in group

            pct_rank = _percent_rank(values)
            if invert:
                pct_rank = 1 - pct_rank

            for cid, val, pr in zip(group_df["company_id"], values, pct_rank):
                rows.append({
                    "company_id": cid,
                    "peer_group_name": group_name,
                    "metric": metric,
                    "value": val if pd.notna(val) else None,
                    "percentile_rank": round(pr, 4) if pd.notna(pr) else None,
                    "year": group_df.loc[group_df["company_id"] == cid, "year"].iloc[0],
                })

    if own_conn:
        conn.close()
    return pd.DataFrame(rows)


def get_company_peer_status(company_id: str, conn=None) -> str:
    """Returns a human-readable status - 'No peer group assigned' if the
    company isn't in any of the 11 groups, else the group name(s)."""
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)
    groups = pd.read_sql(
        "SELECT peer_group_name FROM peer_groups WHERE company_id = ?", conn, params=(company_id,)
    )
    if own_conn:
        conn.close()
    if groups.empty:
        return "No peer group assigned"
    return ", ".join(groups["peer_group_name"].tolist())


def write_to_db(df: pd.DataFrame, conn=None):
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS peer_percentiles (
            company_id TEXT NOT NULL,
            peer_group_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL,
            percentile_rank REAL,
            year TEXT,
            PRIMARY KEY (company_id, peer_group_name, metric)
        )
    """)
    conn.execute("DELETE FROM peer_percentiles")
    df.to_sql("peer_percentiles", conn, if_exists="append", index=False)
    conn.commit()
    if own_conn:
        conn.close()


if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    result = build_peer_percentiles(conn)
    write_to_db(result, conn)
    print(f"peer_percentiles populated: {len(result)} rows")
    print(f"Peer groups covered: {result['peer_group_name'].nunique()} / 11")
    print(f"Companies covered: {result['company_id'].nunique()}")

    # sanity: companies NOT in build_universe's peer_groups membership
    all_companies = pd.read_sql("SELECT id FROM companies", conn)["id"].tolist()
    covered = set(result["company_id"].unique())
    uncovered = [c for c in all_companies if c not in covered]
    print(f"\nCompanies with no peer group ({len(uncovered)}):")
    for c in uncovered[:5]:
        print(f"  {c}: {get_company_peer_status(c, conn)}")
    print("  ...")

    conn.close()