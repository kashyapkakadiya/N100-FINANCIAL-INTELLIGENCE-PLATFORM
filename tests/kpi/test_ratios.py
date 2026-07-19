import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from analytics.ratios import (
    net_profit_margin, operating_profit_margin, opm_cross_check,
    return_on_equity, return_on_capital_employed, return_on_assets,
    debt_to_equity, high_leverage_flag, interest_coverage, icr_risk_flag,
    net_debt, asset_turnover,
)

# --- Day 8: Profitability ---

def test_npm_normal():
    assert net_profit_margin(1000, 100) == 10.0

def test_npm_zero_sales():
    assert net_profit_margin(0, 100) is None

def test_opm_cross_check_mismatch():
    computed = operating_profit_margin(1000, 250)  # 25.0
    diff = opm_cross_check(computed, 21.5)
    assert diff > 1.0

def test_opm_cross_check_ok():
    computed = operating_profit_margin(1000, 215)  # 21.5
    diff = opm_cross_check(computed, 21.5)
    assert diff < 1.0

def test_roe_normal():
    assert return_on_equity(100, 10, 90) == 100.0  # 100 / (10+90) * 100

def test_roe_negative_equity():
    assert return_on_equity(100, 10, -200) is None

def test_roce_normal():
    # EBIT = 200 - 20 = 180; capital = 100+400+500 = 1000; ROCE = 18%
    assert return_on_capital_employed(200, 20, 100, 400, 500) == 18.0

def test_roa_zero_assets():
    assert return_on_assets(100, 0) is None


# --- Day 9: Leverage & Efficiency ---

def test_de_debtfree():
    assert debt_to_equity(0, 100, 400) == 0

def test_de_normal():
    assert debt_to_equity(500, 100, 400) == 1.0

def test_de_negative_equity_with_debt():
    assert debt_to_equity(500, 10, -50) is None

def test_high_leverage_flag_nonfinancial():
    assert high_leverage_flag(6.0, "Industrials") is True

def test_high_leverage_flag_financial_exempt():
    assert high_leverage_flag(6.0, "Financials") is False

def test_icr_debtfree():
    icr, label = interest_coverage(500, 50, 0)
    assert icr is None
    assert label == "Debt Free"

def test_icr_normal():
    icr, label = interest_coverage(500, 50, 100)
    assert icr == 5.5

def test_icr_risk_flag():
    assert icr_risk_flag(1.2) is True
    assert icr_risk_flag(3.0) is False
    assert icr_risk_flag(None) is False

def test_asset_turnover_zero():
    assert asset_turnover(1000, 0) is None

def test_net_debt():
    assert net_debt(500, 200) == 300