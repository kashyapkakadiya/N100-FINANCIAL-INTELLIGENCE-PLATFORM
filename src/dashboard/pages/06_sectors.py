"""
pages/06_sectors.py — Module 5, Day 25: Sector Analysis screen.
"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from dashboard.utils import db

st.title("Sector Analysis")

sectors = db.get_sectors()
sector_names = sorted(sectors["broad_sector"].dropna().unique())
selected_sector = st.selectbox("Sector", sector_names)

conn = sqlite3.connect("data/nifty100.db")
ratios = pd.read_sql("""
    SELECT f.*, s.broad_sector, s.sub_sector, c.company_name FROM financial_ratios f
    LEFT JOIN sectors s ON f.company_id = s.company_id
    LEFT JOIN companies c ON f.company_id = c.id
    WHERE f.net_profit_margin_pct IS NOT NULL
    AND f.year = (SELECT MAX(year) FROM financial_ratios f2
                  WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
""", conn)
pl = pd.read_sql("SELECT company_id, year, sales FROM profitandloss", conn)
mc = pd.read_sql("SELECT company_id, cal_year, market_cap_crore FROM market_cap", conn)
mc_latest = mc.sort_values("cal_year").groupby("company_id").tail(1)
conn.close()

sector_df = ratios[ratios["broad_sector"] == selected_sector].merge(pl, on=["company_id", "year"], how="left")
sector_df = sector_df.merge(mc_latest, on="company_id", how="left")

if sector_df.empty:
    st.info("No data available for this sector.")
    st.stop()

st.markdown("---")
st.subheader(f"{selected_sector} — Revenue vs ROE (bubble size = Market Cap)")
plot_df = sector_df.dropna(subset=["sales", "return_on_equity_pct", "market_cap_crore"])
if plot_df.empty:
    st.info("Not enough data (revenue, ROE, and market cap all required) to plot the bubble chart.")
else:
    fig = px.scatter(
        plot_df, x="sales", y="return_on_equity_pct", size="market_cap_crore",
        color="sub_sector", hover_name="company_name",
        labels={"sales": "Revenue (₹ Cr)", "return_on_equity_pct": "ROE %", "market_cap_crore": "Market Cap"},
        size_max=50,
    )
    fig.update_layout(height=500)
    st.plotly_chart(fig, width='stretch')

st.markdown("---")
st.subheader(f"{selected_sector} — Median KPIs")
median_metrics = {
    "ROE %": sector_df["return_on_equity_pct"].median(),
    "ROCE %": sector_df["return_on_capital_employed_pct"].median(),
    "NPM %": sector_df["net_profit_margin_pct"].median(),
    "D/E": sector_df["debt_to_equity"].median(),
    "Revenue CAGR 5yr %": sector_df["revenue_cagr_5yr"].median(),
}
bar_df = pd.DataFrame({"Metric": list(median_metrics.keys()), "Median Value": list(median_metrics.values())})
fig2 = px.bar(bar_df, x="Metric", y="Median Value", text_auto=".1f")
fig2.update_layout(height=350)
st.plotly_chart(fig2, width='stretch')

st.caption(f"{sector_df['company_id'].nunique()} companies in {selected_sector}.")