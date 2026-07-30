"""
pages/01_home.py — Module 5, Day 23: Home / Overview screen.
Year selector maps a plain calendar year (2019-2024) to the March-ending
fiscal year string ('YYYY-03') for financial_ratios, and directly to
cal_year for market_cap. Non-March fiscal year-end companies (e.g. SIEMENS)
will show N/A in years where their March-equivalent row doesn't exist.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard.utils import db

st.title("Home / Overview")

with st.sidebar:
    st.subheader("Year")
    selected_year = st.selectbox("Fiscal year (March close)", options=[2024, 2023, 2022, 2021, 2020, 2019], index=0)

fy_string = f"{selected_year}-03"
ratios = db.get_all_ratios_for_fy(fy_string)
market_cap = db.get_all_market_cap_for_year(selected_year)

if ratios.empty:
    st.warning(f"No financial_ratios data found for {fy_string}. Try a different year.")
    st.stop()

# "Average ROE" uses a winsorized mean (cap at P95), not a raw arithmetic
# mean. Found during testing: BEL (4744%) and HAL (3816%) - the same
# extreme-capital-structure anomalies already documented in Sprint 2's
# ratio_edge_cases.log - distort a raw mean to 125%, when the median is a
# sane 16.3%. Same winsorization principle used for the composite score
# elsewhere in this codebase, applied here so the first number on the
# dashboard isn't visibly wrong.
roe_for_avg = ratios["return_on_equity_pct"].dropna()
roe_p95 = roe_for_avg.quantile(0.95) if len(roe_for_avg) else None
avg_roe = roe_for_avg.clip(upper=roe_p95).mean() if roe_p95 is not None else None

median_pe = market_cap["pe_ratio"].median() if not market_cap.empty else None
median_de = ratios["debt_to_equity"].median()
total_companies = ratios["company_id"].nunique()
median_rev_cagr = ratios["revenue_cagr_5yr"].median()
debt_free_count = (ratios["debt_to_equity"] == 0).sum()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
c2.metric("Median P/E", f"{median_pe:.1f}x" if pd.notna(median_pe) else "N/A")
c3.metric("Median D/E", f"{median_de:.2f}" if pd.notna(median_de) else "N/A")
c4.metric("Companies", f"{total_companies}")
c5.metric("Median Revenue CAGR 5yr", f"{median_rev_cagr:.1f}%" if pd.notna(median_rev_cagr) else "N/A")
c6.metric("Debt-Free Companies", f"{debt_free_count}")

st.markdown("---")
col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("Sector Breakdown")
    sectors = db.get_sectors()
    sector_counts = sectors["broad_sector"].value_counts().reset_index()
    sector_counts.columns = ["broad_sector", "count"]
    fig = px.pie(sector_counts, names="broad_sector", values="count", hole=0.5)
    fig.update_layout(showlegend=True, height=420)
    st.plotly_chart(fig, width='stretch')

with col_right:
    st.subheader("Top 5 by Composite Quality Score")
    top5 = ratios.sort_values("composite_quality_score", ascending=False).head(5)
    display = top5[["company_id", "company_name", "broad_sector", "composite_quality_score",
                     "return_on_equity_pct", "debt_to_equity"]].copy()
    display.columns = ["Ticker", "Company", "Sector", "Composite Score", "ROE %", "D/E"]
    st.dataframe(display.set_index("Ticker"), width='stretch', height=250)

st.caption(
    "Stock price and market capitalisation figures are simulated data for this project. "
    "Metrics reflect the March-ending fiscal year closest to the selected year; companies "
    "with a non-March fiscal year end may show N/A for a given year."
)