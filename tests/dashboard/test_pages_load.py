"""
tests/dashboard/test_pages_load.py — Sprint 4 Day 27/28: formal regression
suite for the dashboard, based on the manual QA pass. Run with:
    python -m pytest tests/dashboard/ -v

Uses Streamlit's AppTest API (streamlit.testing.v1) to execute each page
script headlessly and assert zero runtime exceptions. This does NOT
replace a real-browser walkthrough (click interactions, visual layout,
live network calls) - see sprint4_retro.md for what still needs manual
confirmation (Annual Reports' live URL check specifically).
"""
import sys
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PAGES_DIR = PROJECT_ROOT / "src" / "dashboard" / "pages"
APP_FILE = PROJECT_ROOT / "src" / "dashboard" / "app.py"

TEST_TICKERS = [
    "TCS", "INFY",            # IT
    "HDFCBANK", "ICICIBANK",  # Financials
    "HINDUNILVR", "NESTLEIND",  # FMCG
    "RELIANCE", "ONGC",       # Energy
    "SUNPHARMA", "CIPLA",     # Healthcare
]
SPARSE_DATA_TICKERS = ["JIOFIN", "DIVISLAB"]  # 2yr history / 0 documents
TICKER_SEARCH_PAGES = ["02_profile.py", "05_trends.py", "08_reports.py"]
NON_TICKER_PAGES = ["01_home.py", "03_screener.py", "04_peers.py", "06_sectors.py", "07_capital.py"]


@pytest.mark.parametrize("page", NON_TICKER_PAGES)
def test_page_default_load(page):
    at = AppTest.from_file(str(PAGES_DIR / page))
    at.run(timeout=20)
    assert not at.exception, f"{page} raised: {at.exception}"


def test_app_shell_loads():
    at = AppTest.from_file(str(APP_FILE))
    at.run(timeout=20)
    assert not at.exception


@pytest.mark.parametrize("page", TICKER_SEARCH_PAGES)
@pytest.mark.parametrize("ticker", TEST_TICKERS)
def test_ticker_search_pages(page, ticker):
    at = AppTest.from_file(str(PAGES_DIR / page))
    at.run(timeout=20)
    at.text_input[0].input(ticker).run(timeout=20)
    assert not at.exception, f"{page} raised for {ticker}: {at.exception}"


@pytest.mark.parametrize("page", TICKER_SEARCH_PAGES)
@pytest.mark.parametrize("ticker", SPARSE_DATA_TICKERS)
def test_sparse_data_companies_no_crash(page, ticker):
    at = AppTest.from_file(str(PAGES_DIR / page))
    at.run(timeout=20)
    at.text_input[0].input(ticker).run(timeout=20)
    assert not at.exception, f"{page} raised for sparse-data company {ticker}: {at.exception}"


def test_ticker_not_found_shows_friendly_message():
    at = AppTest.from_file(str(PAGES_DIR / "02_profile.py"))
    at.run(timeout=20)
    at.text_input[0].input("ZZZZNOTREAL").run(timeout=20)
    assert not at.exception
    warnings = [w.value for w in at.warning]
    assert "Ticker not found — please try another" in warnings


def test_screener_extreme_slider_values_no_crash():
    at_max = AppTest.from_file(str(PAGES_DIR / "03_screener.py"))
    at_max.run(timeout=20)
    for slider in at_max.slider:
        slider.set_value(slider.max)
    at_max.run(timeout=20)
    assert not at_max.exception

    at_min = AppTest.from_file(str(PAGES_DIR / "03_screener.py"))
    at_min.run(timeout=20)
    for slider in at_min.slider:
        slider.set_value(slider.min)
    at_min.run(timeout=20)
    assert not at_min.exception


def test_screener_default_shows_all_companies():
    """Regression test for the Day 24 bug: untouched sliders must not hide
    companies with a legitimate NaN in an unrelated metric."""
    at = AppTest.from_file(str(PAGES_DIR / "03_screener.py"))
    at.run(timeout=20)
    assert not at.exception
    markdown_text = [m.value for m in at.markdown]
    assert any("92 companies match your filters" in m for m in markdown_text)


def test_screener_reset_button_no_crash():
    """Regression test for the session_state-after-widget-instantiation bug."""
    at = AppTest.from_file(str(PAGES_DIR / "03_screener.py"))
    at.run(timeout=20)
    quality_btn = [b for b in at.button if b.label == "Quality"][0]
    quality_btn.click().run(timeout=20)
    assert not at.exception

    reset_btn = [b for b in at.button if b.label == "Reset all filters"][0]
    reset_btn.click().run(timeout=20)
    assert not at.exception


def test_screener_preset_counts_match_sprint3():
    """Cross-check preset results against the values verified in Sprint 3."""
    expected = {
        "Quality": 22, "Value": 2, "Growth": 19,
        "Dividend": 30, "Debt-Free": 2, "Turnaround": 29,
    }
    for label, expected_count in expected.items():
        at = AppTest.from_file(str(PAGES_DIR / "03_screener.py"))
        at.run(timeout=20)
        btn = [b for b in at.button if b.label == label][0]
        btn.click().run(timeout=20)
        assert not at.exception
        markdown_text = [m.value for m in at.markdown]
        assert any(f"{expected_count} companies match your filters" in m for m in markdown_text), (
            f"Preset '{label}': expected {expected_count}, got {markdown_text}"
        )


def test_company_profile_load_time_under_3s():
    for ticker in ["TCS", "HDFCBANK", "HINDUNILVR", "RELIANCE", "SUNPHARMA"]:
        start = time.perf_counter()
        at = AppTest.from_file(str(PAGES_DIR / "02_profile.py"))
        at.run(timeout=20)
        at.text_input[0].input(ticker).run(timeout=20)
        elapsed = time.perf_counter() - start
        assert not at.exception
        assert elapsed < 3.0, f"{ticker} took {elapsed:.2f}s (headless) - re-check in a real browser too"


def test_peer_comparison_it_services_membership():
    at = AppTest.from_file(str(PAGES_DIR / "04_peers.py"))
    at.run(timeout=20)
    group_sb = at.selectbox[0]
    group_sb.select("IT Services").run(timeout=20)
    assert not at.exception
    company_sb = at.selectbox[1]
    assert set(company_sb.options) == {"TCS", "INFY", "HCLTECH", "TECHM", "LTIM"}