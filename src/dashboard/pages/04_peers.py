"""
pages/04_peers.py — Module 5, Day 24: Peer Comparison screen.
"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from screener.engine import build_universe
from analytics.composite_score import compute_composite_scores

st.title("Peer Comparison")

conn = sqlite3.connect("data/nifty100.db")
universe = build_universe(conn)
universe = compute_composite_scores(universe, conn)
peer_groups = pd.read_sql("SELECT peer_group_name, company_id, is_benchmark FROM peer_groups", conn)
companies = pd.read_sql("SELECT id, company_name FROM companies", conn)

group_names = sorted(peer_groups["peer_group_name"].unique())
selected_group = st.selectbox("Peer group", group_names)

group_df = peer_groups[peer_groups["peer_group_name"] == selected_group].merge(universe, on="company_id", how="inner")
if group_df.empty:
    st.warning("No data available for this peer group.")
    st.stop()

AXES = {
    "ROE": "return_on_equity_pct", "ROCE": "return_on_capital_employed_pct",
    "NPM": "net_profit_margin_pct", "D/E": "debt_to_equity",
    "FCF": "free_cash_flow_cr", "PAT CAGR 5yr": "pat_cagr_5yr",
    "Revenue CAGR 5yr": "revenue_cagr_5yr", "Composite Score": "composite_quality_score_sector",
}
INVERT = {"D/E"}
LABELS = list(AXES.keys())


def _percent_rank(series):
    n = series.notna().sum()
    if n <= 1:
        return pd.Series([1.0 if pd.notna(v) else None for v in series], index=series.index)
    ranks = series.rank(method="min", ascending=True)
    return (ranks - 1) / (n - 1)


scores = pd.DataFrame(index=group_df.index)
for label, col in AXES.items():
    pr = _percent_rank(group_df[col]) * 100
    if label in INVERT:
        pr = 100 - pr
    scores[label] = pr
scores["company_id"] = group_df["company_id"].values

member_options = group_df["company_id"].tolist()
selected_company = st.selectbox("Company", member_options)

company_row = scores[scores["company_id"] == selected_company][LABELS].iloc[0].tolist()
peer_avg = scores[LABELS].mean().tolist()

fig = go.Figure()
fig.add_trace(go.Scatterpolar(r=company_row + [company_row[0]], theta=LABELS + [LABELS[0]],
                                fill="toself", name=selected_company))
fig.add_trace(go.Scatterpolar(r=peer_avg + [peer_avg[0]], theta=LABELS + [LABELS[0]],
                                name="Peer Group Avg", line=dict(dash="dash")))
fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), height=500,
                   title=f"{selected_company} vs {selected_group} Peer Group")
st.plotly_chart(fig, width='stretch')

st.markdown("---")
st.subheader(f"{selected_group} — Side-by-Side KPI Table")

table_cols = ["company_id"] + list(AXES.values())
display = group_df[table_cols].merge(companies, left_on="company_id", right_on="id", how="left")
display = display[["company_id", "company_name"] + list(AXES.values())]
display.columns = ["Ticker", "Company"] + LABELS
benchmark_tickers = set(group_df.loc[group_df["is_benchmark"] == 1, "company_id"])


def _highlight_benchmark(row):
    is_bench = row["Ticker"] in benchmark_tickers
    return ["background-color: #FFD966" if is_bench else "" for _ in row]


styled = display.style.apply(_highlight_benchmark, axis=1).format(precision=2)
st.dataframe(styled, width='stretch', height=300)

conn.close()