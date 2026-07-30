"""
src/dashboard/app.py — Module 5, Day 22: main entry point.
Run with: streamlit run src/dashboard/app.py
Streamlit auto-discovers the sibling pages/ directory and builds sidebar
navigation from the numbered files there - no manual navigation code needed.
"""
import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Nifty 100 Financial Intelligence Platform")
st.markdown("""
Welcome. Use the sidebar to navigate between screens:

- **Home** — portfolio-wide summary KPIs and sector breakdown
- **Company Profile** — search any of the 92 companies for a full financial workup
- **Screener** — filter companies by 10 configurable metrics, or apply a preset
- **Peer Comparison** — radar chart and side-by-side table within a peer group
- **Trend Analysis** — multi-metric historical trends for one company
- **Sector Analysis** — sector-level bubble chart and median KPIs
- **Capital Allocation Map** — treemap of capital allocation patterns across all 92 companies
- **Annual Reports** — links to filed annual reports per company

*All monetary values are in Indian Rupees - Crore (Cr) unless otherwise stated.
Stock price and market cap figures are simulated data for this project.*
""")

st.info("Select a screen from the sidebar to get started.")