"""
pages/02_profile.py — Module 5, Day 23: Company Profile screen.
Pros/cons rows are NOT always paired (TCS has a pro with no corresponding
con on the same row) - badges only render for non-null values.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dashboard.utils import db

st.title("Company Profile")

companies = db.get_companies()

search_query = st.text_input("Search by company name or ticker", placeholder="e.g. TCS or Tata Consultancy")

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
    selected_label = st.selectbox("Select company", options)
    ticker = selected_label.split(" — ")[0]
else:
    ticker = st.selectbox(
        "Or pick from the list",
        options=(companies["id"] + " — " + companies["company_name"]).tolist(),
    ).split(" — ")[0]

row = companies[companies["id"] == ticker]
if row.empty:
    st.warning("Ticker not found — please try another")
    st.stop()
row = row.iloc[0]

st.markdown("---")
st.subheader(f"{row['company_name']} ({ticker})")
c1, c2 = st.columns([1, 3])
with c1:
    st.write(f"**Sector:** {row['broad_sector'] or 'N/A'}")
    st.write(f"**Sub-sector:** {row['sub_sector'] or 'N/A'}")
    if row["website"]:
        st.write(f"[Website]({row['website']})")
with c2:
    st.write(row["about_company"] or "No description available.")

latest = db.get_latest_ratios(ticker)
st.markdown("---")
if latest.empty:
    st.info("No computed KPI data available for this company.")
else:
    r = latest.iloc[0]
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    def fmt(v, suffix=""):
        return f"{v:.1f}{suffix}" if pd.notna(v) else "N/A"
    k1.metric("ROE", fmt(r["return_on_equity_pct"], "%"))
    k2.metric("ROCE", fmt(r["return_on_capital_employed_pct"], "%"))
    k3.metric("Net Profit Margin", fmt(r["net_profit_margin_pct"], "%"))
    k4.metric("D/E", fmt(r["debt_to_equity"]))
    k5.metric("Revenue CAGR 5yr", fmt(r["revenue_cagr_5yr"], "%") if r["revenue_cagr_5yr"] is not None else "N/A")
    k6.metric("FCF (₹ Cr)", fmt(r["free_cash_flow_cr"]))

st.markdown("---")
st.subheader("Revenue & Net Profit (10yr)")
pl = db.get_pl(ticker).tail(10)
if pl.empty:
    st.info("No P&L history available.")
else:
    fig = go.Figure()
    fig.add_bar(x=pl["year"], y=pl["sales"], name="Revenue")
    fig.add_bar(x=pl["year"], y=pl["net_profit"], name="Net Profit")
    fig.update_layout(barmode="group", height=400, yaxis_title="₹ Crore")
    st.plotly_chart(fig, width='stretch')

st.subheader("ROE & ROCE Trend (10yr)")
hist = db.get_ratios(ticker).tail(10)
hist = hist[hist["return_on_equity_pct"].notna() | hist["return_on_capital_employed_pct"].notna()]
if hist.empty:
    st.info("No ROE/ROCE history available.")
else:
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])
    fig2.add_trace(go.Scatter(x=hist["year"], y=hist["return_on_equity_pct"], name="ROE %", mode="lines+markers"), secondary_y=False)
    fig2.add_trace(go.Scatter(x=hist["year"], y=hist["return_on_capital_employed_pct"], name="ROCE %", mode="lines+markers"), secondary_y=True)
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, width='stretch')

st.markdown("---")
st.subheader("Pros & Cons")
pc = db.get_pros_cons(ticker)
if pc.empty:
    st.caption("No qualitative pros/cons recorded for this company yet.")
else:
    col_p, col_c = st.columns(2)
    with col_p:
        for pro in pc["pros"].dropna():
            st.success(f"✅ {pro}")
    with col_c:
        for con in pc["cons"].dropna():
            st.error(f"❌ {con}")