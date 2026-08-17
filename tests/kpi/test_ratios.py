"""
tests/kpi/test_ratios.py — Day 41: 20+ unit tests covering the KPI formula
edge cases explicitly named in the spec: ROE with positive/negative equity,
D/E for debt-free companies, ICR when interest=0, D/E>5 flag for
non-financial companies, CAGR turnaround/decline-to-loss/normal, OPM
cross-check divergence, CFO quality score.
"""
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
from analytics.cagr import compute_cagr
from analytics.cashflow_kpis import cfo_quality_score


# --- ROE: positive and negative equity ---

def test_roe_positive_equity():
    assert return_on_equity(100, 10, 90) == 100.0  # 100 / (10+90) * 100

def test_roe_negative_equity_returns_none():
    assert return_on_equity(100, 10, -200) is None

def test_roe_zero_equity_returns_none():
    assert return_on_equity(100, 0, 0) is None

def test_roe_negative_profit_positive_equity():
    assert return_on_equity(-50, 100, 400) == -10.0


# --- D/E: debt-free and D/E>5 flag ---

def test_de_debtfree_returns_zero():
    assert debt_to_equity(0, 100, 400) == 0

def test_de_normal_calculation():
    assert debt_to_equity(500, 100, 400) == 1.0

def test_de_negative_equity_with_debt_returns_none():
    assert debt_to_equity(500, 10, -50) is None

def test_high_leverage_flag_triggers_for_nonfinancial():
    assert high_leverage_flag(6.0, "Industrials") is True

def test_high_leverage_flag_exempt_for_financials():
    assert high_leverage_flag(6.0, "Financials") is False

def test_high_leverage_flag_false_at_exactly_5():
    assert high_leverage_flag(5.0, "Industrials") is False


# --- ICR: interest=0 ---

def test_icr_interest_zero_returns_none_debtfree_label():
    icr, label = interest_coverage(500, 50, 0)
    assert icr is None
    assert label == "Debt Free"

def test_icr_normal_calculation():
    icr, label = interest_coverage(500, 50, 100)
    assert icr == 5.5

def test_icr_risk_flag_below_threshold():
    assert icr_risk_flag(1.2) is True

def test_icr_risk_flag_above_threshold():
    assert icr_risk_flag(3.0) is False

def test_icr_risk_flag_none_is_false():
    assert icr_risk_flag(None) is False


# --- CAGR: turnaround, decline-to-loss, normal ---

def test_cagr_turnaround_flag():
    cagr, flag = compute_cagr(-100, 200, 5)
    assert cagr is None
    assert flag == "TURNAROUND"

def test_cagr_decline_to_loss_flag():
    cagr, flag = compute_cagr(100, -50, 5)
    assert cagr is None
    assert flag == "DECLINE_TO_LOSS"

def test_cagr_normal_calculation():
    cagr, flag = compute_cagr(100, 161.05, 5)
    assert flag is None
    assert round(cagr, 1) == 10.0

def test_cagr_zero_base_flag():
    cagr, flag = compute_cagr(0, 100, 5)
    assert cagr is None
    assert flag == "ZERO_BASE"


# --- OPM cross-check divergence ---

def test_opm_cross_check_flags_divergence():
    computed = operating_profit_margin(1000, 250)  # 25.0
    diff = opm_cross_check(computed, 21.5)
    assert diff > 1.0

def test_opm_cross_check_no_flag_within_tolerance():
    computed = operating_profit_margin(1000, 215)  # 21.5
    diff = opm_cross_check(computed, 21.5)
    assert diff < 1.0


# --- CFO Quality Score ---

def test_cfo_quality_score_high_quality():
    assert cfo_quality_score([120, 130], [100, 100]) == "High Quality"

def test_cfo_quality_score_accrual_risk():
    assert cfo_quality_score([30, 40], [100, 100]) == "Accrual Risk"

def test_cfo_quality_score_moderate():
    assert cfo_quality_score([60, 70], [100, 100]) == "Moderate"

def test_cfo_quality_score_none_when_no_valid_pat():
    assert cfo_quality_score([100], [0]) is None