"""
tests/dq/test_rules.py — Day 41: 14 unit tests, one per DQ rule (DQ-01
through DQ-14). Each test crafts a minimal DataFrame that violates exactly
that rule and verifies the correct rule_id and severity are returned.

Note: DQ-07 and DQ-08 (year/ticker format) are validated at the point of
normalisation (normaliser.py), not against a pre-built DataFrame like the
other 12 rules - tested here via the validator's wrapper functions, which
take an already-known-bad raw value directly (matching how loader.py
actually calls them).
"""
import sys
from pathlib import Path
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from etl.validator import (
    dq01_company_pk_uniqueness, dq02_annual_pk_uniqueness, dq03_fk_integrity,
    dq04_balance_sheet_balance, dq05_opm_cross_check, dq06_positive_sales,
    dq07_unparseable_year, dq08_unparseable_ticker, dq09_net_cash_check,
    dq10_nonneg_fixed_assets, dq11_tax_rate_range, dq12_dividend_payout_cap,
    dq13_url_validity, dq14_eps_sign_consistency,
)


def test_dq01_company_pk_uniqueness():
    df = pd.DataFrame({"id": ["TCS", "TCS", "INFY"]})
    violations = dq01_company_pk_uniqueness(df)
    assert len(violations) >= 1
    assert violations[0]["rule_id"] == "DQ-01"
    assert violations[0]["severity"] == "CRITICAL"


def test_dq02_annual_pk_uniqueness():
    df = pd.DataFrame({
        "company_id": ["TCS", "TCS", "INFY"],
        "year": ["2024-03", "2024-03", "2024-03"],
    })
    violations = dq02_annual_pk_uniqueness(df, "profitandloss")
    assert len(violations) == 2  # both TCS rows flagged
    assert violations[0]["rule_id"] == "DQ-02"
    assert violations[0]["severity"] == "CRITICAL"


def test_dq03_fk_integrity():
    df = pd.DataFrame({"company_id": ["TCS", "FAKECO"], "year": ["2024-03", "2024-03"]})
    valid_ids = {"TCS", "INFY"}
    violations = dq03_fk_integrity(df, "profitandloss", valid_ids)
    assert len(violations) == 1
    assert violations[0]["company_id"] == "FAKECO"
    assert violations[0]["rule_id"] == "DQ-03"
    assert violations[0]["severity"] == "CRITICAL"


def test_dq04_balance_sheet_balance():
    df = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2024-03"],
        "total_assets": [1000.0], "total_liabilities": [1020.0],  # 2% off, exceeds 1% tolerance
    })
    violations = dq04_balance_sheet_balance(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-04"
    assert violations[0]["severity"] == "WARNING"


def test_dq05_opm_cross_check():
    df = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2024-03"],
        "sales": [1000.0], "operating_profit": [250.0],  # computed OPM = 25%
        "opm_percentage": [21.5],  # reported 21.5%, diff = 3.5pt > 1.0
    })
    violations = dq05_opm_cross_check(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-05"
    assert violations[0]["severity"] == "WARNING"


def test_dq06_positive_sales():
    df = pd.DataFrame({"company_id": ["STEELCO"], "year": ["2024-03"], "sales": [-50.0]})
    violations = dq06_positive_sales(df, financial_tickers=set())
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-06"
    assert violations[0]["severity"] == "WARNING"


def test_dq07_unparseable_year():
    violation = dq07_unparseable_year("TCS", "profitandloss", "TTM")
    assert violation["rule_id"] == "DQ-07"
    assert violation["severity"] == "CRITICAL"
    assert violation["raw_value"] == "TTM"


def test_dq08_unparseable_ticker():
    violation = dq08_unparseable_ticker("profitandloss", "T")  # too short
    assert violation["rule_id"] == "DQ-08"
    assert violation["severity"] == "CRITICAL"


def test_dq09_net_cash_check():
    df = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2024-03"],
        "operating_activity": [100.0], "investing_activity": [-50.0], "financing_activity": [-20.0],
        "net_cash_flow": [100.0],  # should be 30, off by 70 > 10 tolerance
    })
    violations = dq09_net_cash_check(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-09"
    assert violations[0]["severity"] == "WARNING"


def test_dq10_nonneg_fixed_assets():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["2024-03"], "fixed_assets": [-10.0]})
    violations = dq10_nonneg_fixed_assets(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-10"
    assert violations[0]["severity"] == "WARNING"


def test_dq11_tax_rate_range():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["2024-03"], "tax_percentage": [75.0]})  # > 60
    violations = dq11_tax_rate_range(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-11"
    assert violations[0]["severity"] == "WARNING"


def test_dq12_dividend_payout_cap():
    df = pd.DataFrame({"company_id": ["TCS"], "year": ["2024-03"], "dividend_payout": [250.0]})  # > 200
    violations = dq12_dividend_payout_cap(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-12"
    assert violations[0]["severity"] == "WARNING"


def test_dq13_url_validity():
    df = pd.DataFrame({"company_id": ["TCS"], "report_year": [2024], "annual_report": [None]})
    violations = dq13_url_validity(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-13"
    assert violations[0]["severity"] == "WARNING"


def test_dq14_eps_sign_consistency():
    df = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2024-03"],
        "net_profit": [500.0], "eps": [-2.0],  # positive profit, negative EPS
    })
    violations = dq14_eps_sign_consistency(df)
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "DQ-14"
    assert violations[0]["severity"] == "WARNING"


# --- Negative control: a clean DataFrame should trigger zero violations ---

def test_dq04_no_violation_when_balanced():
    df = pd.DataFrame({
        "company_id": ["TCS"], "year": ["2024-03"],
        "total_assets": [1000.0], "total_liabilities": [1000.0],
    })
    assert dq04_balance_sheet_balance(df) == []