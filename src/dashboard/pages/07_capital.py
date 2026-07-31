"""
pages/07_capital.py — Module 5, Day 25: Capital Allocation Map screen.
Dropdown is the reliable primary control; on_select="rerun" also wires up
real treemap clicks in the browser, but that path can't be verified
headless so the dropdown guarantees the "click a pattern, see the list"
requirement regardless of click-event quirks.
"""
import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

st.title("Capital Allocation Map")

conn = sqlite3.connect("data/nifty100.db")
df = pd.read_sql("""
    SELECT f.company_id, c.company_name, s.broad_sector, f.capital_allocation_label
    FROM financial_ratios f
    LEFT JOIN companies c ON f.company_id = c.id
    LEFT JOIN sectors s ON f.company_id = s.company_id
    WHERE f.net_profit_margin_pct IS NOT NULL
    AND f.year = (SELECT MAX(year) FROM financial_ratios f2
                  WHERE f2.company_id = f.company_id AND f2.net_profit_margin_pct IS NOT NULL)
""", conn)
conn.close()

if df.empty:
    st.info("No capital allocation data available.")
    st.stop()

st.markdown(f"### {df['company_id'].nunique()} companies across {df['capital_allocation_label'].nunique()} patterns")

fig = px.treemap(
    df, path=[px.Constant("All Companies"), "capital_allocation_label", "company_id"],
    color="capital_allocation_label",
)
fig.update_layout(height=550)
event = st.plotly_chart(fig, width='stretch', on_select="rerun", key="capital_treemap")

st.markdown("---")
st.subheader("Drill Down by Pattern")
selected_pattern = st.selectbox(
    "Select a capital allocation pattern to see its companies",
    options=sorted(df["capital_allocation_label"].dropna().unique()),
)

if event and event.get("selection", {}).get("points"):
    clicked_labels = [p.get("label") for p in event["selection"]["points"]]
    matching = [l for l in clicked_labels if l in df["capital_allocation_label"].values]
    if matching:
        selected_pattern = matching[0]

pattern_df = df[df["capital_allocation_label"] == selected_pattern][["company_id", "company_name", "broad_sector"]]
pattern_df.columns = ["Ticker", "Company", "Sector"]
st.dataframe(pattern_df.set_index("Ticker"), width='stretch', height=300)
st.caption(f"{len(pattern_df)} companies with the '{selected_pattern}' capital allocation pattern.")