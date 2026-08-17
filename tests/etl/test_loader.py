"""
tests/etl/test_loader.py — Day 41: 10 tests verifying the loader reads
correct row counts and column names for each of the 12 source files.

Row count expectations come from the project doc's Dataset Catalogue
(Section 5/6) and are cross-checked against what Sprint 1 actually found
in the real files, which matched the doc exactly.
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from etl.loader import (
    load_companies_raw, load_profitandloss_raw, load_balancesheet_raw,
    load_cashflow_raw, load_analysis_raw, load_documents_raw,
    load_prosandcons_raw, load_sectors_raw, load_stock_prices_raw,
    load_market_cap_raw, load_financial_ratios_raw, load_peer_groups_raw,
)


def test_companies_row_count_and_columns():
    df = load_companies_raw()
    assert len(df) == 92
    expected_cols = {"id", "company_name", "face_value", "book_value", "roce_percentage", "roe_percentage"}
    assert expected_cols.issubset(set(df.columns))


def test_profitandloss_row_count_and_columns():
    df = load_profitandloss_raw()
    assert len(df) == 1276
    expected_cols = {"company_id", "year", "sales", "net_profit", "eps", "operating_profit"}
    assert expected_cols.issubset(set(df.columns))


def test_balancesheet_row_count_and_columns():
    df = load_balancesheet_raw()
    assert len(df) == 1312
    expected_cols = {"company_id", "year", "equity_capital", "reserves", "borrowings", "total_assets"}
    assert expected_cols.issubset(set(df.columns))


def test_cashflow_row_count_and_columns():
    df = load_cashflow_raw()
    assert len(df) == 1187
    expected_cols = {"company_id", "year", "operating_activity", "investing_activity", "financing_activity"}
    assert expected_cols.issubset(set(df.columns))


def test_analysis_row_count_and_columns():
    df = load_analysis_raw()
    assert len(df) == 20
    expected_cols = {"company_id", "compounded_sales_growth", "compounded_profit_growth", "stock_price_cagr", "roe"}
    assert expected_cols.issubset(set(df.columns))


def test_documents_row_count_and_columns():
    df = load_documents_raw()
    assert len(df) == 1585
    expected_cols = {"company_id", "Year", "Annual_Report"}
    assert expected_cols.issubset(set(df.columns))


def test_prosandcons_row_count_and_columns():
    df = load_prosandcons_raw()
    assert len(df) == 16
    expected_cols = {"company_id", "pros", "cons"}
    assert expected_cols.issubset(set(df.columns))


def test_sectors_row_count_and_columns():
    df = load_sectors_raw()
    assert len(df) == 92
    expected_cols = {"company_id", "broad_sector", "sub_sector", "market_cap_category"}
    assert expected_cols.issubset(set(df.columns))


def test_stock_prices_row_count_and_columns():
    df = load_stock_prices_raw()
    assert len(df) == 5520
    expected_cols = {"company_id", "date", "open_price", "close_price", "volume"}
    assert expected_cols.issubset(set(df.columns))


def test_market_cap_peer_groups_financial_ratios_row_counts():
    """Combined test for the three smallest supporting files."""
    mc = load_market_cap_raw()
    assert len(mc) == 552
    assert {"company_id", "year", "pe_ratio", "pb_ratio"}.issubset(set(mc.columns))

    pg = load_peer_groups_raw()
    assert len(pg) == 56
    assert {"peer_group_name", "company_id", "is_benchmark"}.issubset(set(pg.columns))

    fr = load_financial_ratios_raw()
    assert len(fr) == 1184
    assert {"company_id", "year", "net_profit_margin_pct", "return_on_equity_pct"}.issubset(set(fr.columns))