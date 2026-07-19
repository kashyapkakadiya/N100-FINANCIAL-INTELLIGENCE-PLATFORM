import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from analytics.cashflow_kpis import (
    free_cash_flow, cfo_quality_score, capex_intensity,
    fcf_conversion_rate, classify_capital_allocation,
)

def test_fcf_negative_allowed():
    assert free_cash_flow(100, -150) == -50

def test_cfo_quality_high():
    assert cfo_quality_score([120, 130], [100, 100]) == "High Quality"

def test_cfo_quality_accrual_risk():
    assert cfo_quality_score([30, 40], [100, 100]) == "Accrual Risk"

def test_cfo_quality_none_when_no_valid_pat():
    assert cfo_quality_score([100], [0]) is None

def test_capex_intensity_asset_light():
    result = capex_intensity(-20, 1000)  # 2%
    assert result["label"] == "Asset Light"

def test_capex_intensity_capital_intensive():
    result = capex_intensity(-150, 1000)  # 15%
    assert result["label"] == "Capital Intensive"

def test_capex_intensity_zero_sales():
    assert capex_intensity(-20, 0) is None

def test_fcf_conversion_zero_op_profit():
    assert fcf_conversion_rate(50, 0) is None

def test_capital_allocation_reinvestor():
    result = classify_capital_allocation(100, -50, -30, cfo_pat_ratio=0.8)
    assert result["pattern_label"] == "Reinvestor"

def test_capital_allocation_shareholder_returns():
    result = classify_capital_allocation(100, -50, -30, cfo_pat_ratio=1.5)
    assert result["pattern_label"] == "Shareholder Returns"

def test_capital_allocation_distress():
    result = classify_capital_allocation(-50, 100, 80)
    assert result["pattern_label"] == "Distress Signal"

def test_capital_allocation_pre_revenue():
    result = classify_capital_allocation(-10, -20, -30)
    assert result["pattern_label"] == "Pre-Revenue"