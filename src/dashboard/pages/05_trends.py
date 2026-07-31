"""
pages/05_trends.py — Module 5, Day 25: Trend Analysis screen.
Multiple metrics are indexed to first year = 100 when more than one is
selected, since ROE % and Revenue Cr are on incompatible scales. YoY %
annotated only for the first selected metric to avoid label clutter.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dashboard.utils import db

st.title("Trend Analysis")

companies = db.get_companies()
search_query = st.text_input("Search by company name or ticker", placeholder="e.g. TCS")

if search_query:
    q = search_query.strip().upper()
    matches = companies[
        companies["id"].str.upper().str.contains(q, na=False)
        | companies["company_name"].str.upper().str.contains(q, na=False)
    ]
    if matches.empty:
        st.warning("Ticker not found — please try another")
        st.stop()
    options = (matches["id"] + " — " + matches["company_name"]).tolist()
    ticker = st.selectbox("Select company", options).split(" — ")[0]
else:
    ticker = st.selectbox("Or pick from the list", (companies["id"] + " — " + companies["company_name"]).tolist()).split(" — ")[0]

pl = db.get_pl(ticker)
ratios = db.get_ratios(ticker)
merged = pl.merge(ratios, on=["company_id", "year"], how="outer", suffixes=("", "_r")).sort_values("year")

METRIC_OPTIONS = {
    "Revenue (₹Cr)": "sales",
    "Net Profit (₹Cr)": "net_profit",
    "ROE %": "return_on_equity_pct",
    "ROCE %": "return_on_capital_employed_pct",
    "Net Profit Margin %": "net_profit_margin_pct",
    "D/E": "debt_to_equity",
    "Free Cash Flow (₹Cr)": "free_cash_flow_cr",
    "EPS (₹)": "eps",
}

st.markdown("---")
selected_labels = st.multiselect(
    "Select up to 3 metrics to overlay", options=list(METRIC_OPTIONS.keys()),
    default=["Revenue (₹Cr)", "Net Profit (₹Cr)"], max_selections=3,
)

if not selected_labels:
    st.info("Select at least one metric above.")
    st.stop()

plot_df = merged.tail(10).copy()
if plot_df.empty:
    st.info("No historical data available for this company.")
    st.stop()

fig = go.Figure()
for i, label in enumerate(selected_labels):
    col = METRIC_OPTIONS[label]
    series = plot_df[col]
    if len(selected_labels) > 1:
        base = series.dropna().iloc[0] if series.notna().any() else None
        y_vals = (series / base * 100) if base not in (None, 0) else series
        y_label = "Indexed (first year = 100)"
    else:
        y_vals = series
        y_label = label

    yoy_pct = series.pct_change() * 100
    text_labels = [f"{v:+.1f}%" if pd.notna(v) else "" for v in yoy_pct] if i == 0 else None

    fig.add_trace(go.Scatter(
        x=plot_df["year"], y=y_vals, mode="lines+markers+text" if i == 0 else "lines+markers",
        name=label, text=text_labels, textposition="top center",
    ))

fig.update_layout(height=450, yaxis_title=y_label if len(selected_labels) > 1 else selected_labels[0])
st.plotly_chart(fig, width='stretch')

if len(selected_labels) > 1:
    st.caption(
        "Multiple metrics are shown indexed to their first available year = 100, "
        "since raw values span very different scales. YoY % change labels are shown "
        "only for the first selected metric to keep the chart readable."
    )
else:
    st.caption("YoY % change is annotated at each data point.")