"""
pages/03_screener.py — Module 5, Day 24: Screener screen.
Slider ranges are capped at practical bounds, not literal data min/max
(ROE max is 4744% - BEL, Sprint 2's known anomaly - a literal-range slider
would be unusable). Preset buttons set st.session_state before sliders are
instantiated, then rerun.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd
import sqlite3
from screener.engine import build_universe, load_config, apply_filters
from analytics.composite_score import compute_composite_scores

st.title("Financial Screener")

config = load_config()
conn = sqlite3.connect("data/nifty100.db")
universe = build_universe(conn)
universe = compute_composite_scores(universe, conn)
conn.close()

SLIDER_DEFS = {
    "min_roe":               ("ROE min (%)",              -20.0, 100.0, -20.0, 1.0),
    "max_de":                ("D/E max",                    0.0,  15.0,  15.0, 0.1),
    "min_fcf":                ("FCF min (₹ Cr)",       -100000.0, 50000.0, -100000.0, 1000.0),
    "min_revenue_cagr_5yr":     ("Revenue CAGR 5yr min (%)",  -20.0,  50.0, -20.0, 1.0),
    "min_pat_cagr_5yr":         ("PAT CAGR 5yr min (%)",      -30.0, 130.0, -30.0, 1.0),
    "min_opm":                ("OPM min (%)",              -20.0, 100.0, -20.0, 1.0),
    "max_pe":                 ("P/E max",                    5.0,  85.0,  85.0, 1.0),
    "max_pb":                 ("P/B max",                    0.0,  15.0,  15.0, 0.5),
    "min_dividend_yield":       ("Dividend Yield min (%)",     0.0,   5.0,   0.0, 0.1),
    "min_icr":                ("Interest Coverage min",      0.0,  50.0,   0.0, 1.0),
}
PERMISSIVE_DEFAULTS = {k: v[3] for k, v in SLIDER_DEFS.items()}

PRESET_BUTTONS = [
    ("quality_compounder", "Quality"),
    ("value_pick", "Value"),
    ("growth_accelerator", "Growth"),
    ("dividend_champion", "Dividend"),
    ("debt_free_blue_chip", "Debt-Free"),
    ("turnaround_watch", "Turnaround"),
]

with st.sidebar:
    st.subheader("Preset Screens")
    preset_cols = st.columns(2)
    for i, (preset_key, label) in enumerate(PRESET_BUTTONS):
        if preset_cols[i % 2].button(label, use_container_width=True):
            new_values = dict(PERMISSIVE_DEFAULTS)
            preset_filters = config["presets"][preset_key].get("filters", {})
            for fkey, fval in preset_filters.items():
                if fkey in SLIDER_DEFS:
                    new_values[fkey] = float(fval)
            for skey, sval in new_values.items():
                st.session_state[skey] = sval
            st.session_state["_active_preset"] = preset_key
            st.rerun()

    st.subheader("Custom Filters")
    if st.button("Reset all filters"):
        for k, v in PERMISSIVE_DEFAULTS.items():
            st.session_state[k] = v
        st.session_state.pop("_active_preset", None)
        st.rerun()    
    for key, (label, lo, hi, default, step) in SLIDER_DEFS.items():
        if key not in st.session_state:
            st.session_state[key] = default
    slider_values = {}
    for key, (label, lo, hi, default, step) in SLIDER_DEFS.items():
        slider_values[key] = st.slider(label, min_value=lo, max_value=hi, step=step, key=key)

active_preset = st.session_state.get("_active_preset")
if active_preset == "turnaround_watch":
    from screener.engine import screen_turnaround_watch
    result = screen_turnaround_watch(universe, sqlite3.connect("data/nifty100.db"))
else:
    active_filters = {
        key: val for key, val in slider_values.items()
        if val != PERMISSIVE_DEFAULTS[key]
    }
    result = apply_filters(universe, active_filters, config)

st.markdown(f"### {len(result)} companies match your filters")

if result.empty:
    st.info("No companies match the current filter combination. Try loosening a threshold.")
else:
    display_cols = ["company_id", "company_name", "broad_sector", "composite_quality_score_sector",
                     "return_on_equity_pct", "debt_to_equity", "free_cash_flow_cr",
                     "revenue_cagr_5yr", "pe_ratio", "dividend_yield_pct"]
    display = result[display_cols].copy()
    display.columns = ["Ticker", "Company", "Sector", "Composite Score", "ROE %", "D/E",
                        "FCF (₹Cr)", "Rev CAGR 5yr %", "P/E", "Div Yield %"]
    display_shown = display.set_index("Ticker")
    numeric_cols = display_shown.select_dtypes(include="number").columns
    display_shown[numeric_cols] = display_shown[numeric_cols].round(2)
    display_shown = display_shown.astype(str).replace(["nan", "None"], "N/A")
    st.dataframe(display_shown, width='stretch', height=500)

    csv_bytes = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download results as CSV",
        data=csv_bytes,
        file_name="screener_results.csv",
        mime="text/csv",
    )