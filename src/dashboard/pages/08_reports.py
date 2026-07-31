"""
pages/08_reports.py — Module 5, Day 25: Annual Reports screen.
NOTE: could not verify live 200-vs-404 distinction from this sandbox (no
network access to bseindia.com). Confirmed the graceful-failure path works
(caught exception -> treated as unavailable, no crash) but please verify
on your machine that a genuinely dead link shows the red badge correctly.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import requests
from dashboard.utils import db

st.title("Annual Reports")

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


@st.cache_data(ttl=3600, show_spinner=False)
def check_url_alive(url: str) -> bool:
    if not url or not str(url).startswith(("http://", "https://")):
        return False
    try:
        resp = requests.head(url, timeout=4, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


st.markdown("---")
docs = db.get_documents(ticker)

if docs.empty:
    st.info("No annual reports on file for this company.")
else:
    st.subheader(f"Annual Reports — {ticker}")
    for _, row in docs.iterrows():
        col_year, col_link, col_status = st.columns([1, 4, 2])
        col_year.write(f"**{row['report_year']}**")
        if row["annual_report"]:
            col_link.markdown(f"[View PDF]({row['annual_report']})")
            is_alive = check_url_alive(row["annual_report"])
            if is_alive:
                col_status.success("Available")
            else:
                col_status.error("Report unavailable")
        else:
            col_link.write("No URL on file")
            col_status.error("Report unavailable")

st.caption(
    "Link status is checked live against the source URL and cached for 1 hour. "
    "A red 'Report unavailable' badge means either no URL was on file or the "
    "linked PDF did not return a successful response."
)