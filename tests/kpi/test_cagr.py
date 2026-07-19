import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from analytics.cagr import compute_cagr, compute_cagr_for_window


# --- Core formula edge cases (spec decision table) ---

def test_cagr_normal():
    cagr, flag = compute_cagr(100, 161.05, 5)
    assert flag is None
    assert round(cagr, 1) == 10.0

def test_cagr_normal_different_window():
    cagr, flag = compute_cagr(100, 200, 3)
    assert flag is None
    assert round(cagr, 2) == 25.99

def test_cagr_decline_to_zero_computes_normally():
    cagr, flag = compute_cagr(100, 0, 5)
    assert flag is None
    assert cagr == -100.0

def test_cagr_turnaround():
    cagr, flag = compute_cagr(-100, 200, 5)
    assert cagr is None
    assert flag == "TURNAROUND"

def test_cagr_decline_to_loss():
    cagr, flag = compute_cagr(100, -50, 5)
    assert cagr is None
    assert flag == "DECLINE_TO_LOSS"

def test_cagr_both_negative():
    cagr, flag = compute_cagr(-100, -50, 5)
    assert cagr is None
    assert flag == "BOTH_NEGATIVE"

def test_cagr_zero_base():
    cagr, flag = compute_cagr(0, 100, 5)
    assert cagr is None
    assert flag == "ZERO_BASE"

def test_cagr_insufficient_missing_start():
    cagr, flag = compute_cagr(None, 100, 5)
    assert cagr is None
    assert flag == "INSUFFICIENT"

def test_cagr_insufficient_zero_years():
    cagr, flag = compute_cagr(100, 200, 0)
    assert cagr is None
    assert flag == "INSUFFICIENT"


# --- Windowed application (real company-style year series) ---

def test_cagr_window_normal():
    series = {"2019-03": 100, "2020-03": 110, "2021-03": 121,
              "2022-03": 133, "2023-03": 146, "2024-03": 161.05}
    cagr, flag = compute_cagr_for_window(series, 5)
    assert flag is None
    assert round(cagr, 1) == 10.0

def test_cagr_window_insufficient_history():
    series = {"2023-03": 100, "2024-03": 110}  # only 2 years, asking for 5yr
    cagr, flag = compute_cagr_for_window(series, 5)
    assert cagr is None
    assert flag == "INSUFFICIENT"