from __future__ import annotations
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "nifty100.db"

def _connect():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

@st.cache_data(ttl=600, show_spinner=False)
def get_companies() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("""
        SELECT c.id, c.company_name, c.about_company, c.website, c.face_value,
               c.roce_percentage, c.roe_percentage, s.broad_sector, s.sub_sector
        FROM companies c LEFT JOIN sectors s ON c.id = s.company_id
        ORDER BY c.company_name
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_ratios(ticker: str, year: str | None = None) -> pd.DataFrame:
    conn = _connect()
    if year:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?", conn, params=(ticker, year))
    else:
        df = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_latest_ratios(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("""
        SELECT * FROM financial_ratios f1
        WHERE company_id = ? AND net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_pl(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_bs(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_cf(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ? ORDER BY year", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_sectors() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM sectors", conn)
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_peers(group_name: str) -> pd.DataFrame:
    conn = _connect()
    long_df = pd.read_sql("SELECT * FROM peer_percentiles WHERE peer_group_name = ?", conn, params=(group_name,))
    conn.close()
    if long_df.empty:
        return long_df
    wide = long_df.pivot_table(index="company_id", columns="metric", values=["value", "percentile_rank"])
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    return wide.reset_index()

@st.cache_data(ttl=600, show_spinner=False)
def get_valuation(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM market_cap WHERE company_id = ? ORDER BY cal_year", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT pros, cons FROM prosandcons WHERE company_id = ?", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_documents(ticker: str) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT report_year, annual_report FROM documents WHERE company_id = ? ORDER BY report_year DESC", conn, params=(ticker,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_all_latest_ratios() -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("""
        SELECT f1.*, s.broad_sector, s.sub_sector, c.company_name
        FROM financial_ratios f1
        LEFT JOIN sectors s ON f1.company_id = s.company_id
        LEFT JOIN companies c ON f1.company_id = c.id
        WHERE f1.net_profit_margin_pct IS NOT NULL
        AND f1.year = (SELECT MAX(year) FROM financial_ratios f2
                       WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_all_ratios_for_fy(fy_year_str: str) -> pd.DataFrame:
    """All companies' financial_ratios for one specific fiscal year string (e.g. '2024-03')."""
    conn = _connect()
    df = pd.read_sql("""
        SELECT f.*, s.broad_sector, s.sub_sector, c.company_name
        FROM financial_ratios f
        LEFT JOIN sectors s ON f.company_id = s.company_id
        LEFT JOIN companies c ON f.company_id = c.id
        WHERE f.year = ? AND f.net_profit_margin_pct IS NOT NULL
    """, conn, params=(fy_year_str,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_all_market_cap_for_year(cal_year: int) -> pd.DataFrame:
    conn = _connect()
    df = pd.read_sql("SELECT * FROM market_cap WHERE cal_year = ?", conn, params=(cal_year,))
    conn.close()
    return df

@st.cache_data(ttl=600, show_spinner=False)
def get_available_fy_years() -> list:
    conn = _connect()
    years = pd.read_sql(
        "SELECT DISTINCT year FROM financial_ratios WHERE net_profit_margin_pct IS NOT NULL ORDER BY year", conn
    )["year"].tolist()
    conn.close()
    return years