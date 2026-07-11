import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from etl.normaliser import normalize_year, normalize_ticker  # noqa: E402


@pytest.mark.parametrize("raw, expected", [
    ("Mar-23", "2023-03"), ("Mar 23", "2023-03"), ("March-2023", "2023-03"),
    ("March 2023", "2023-03"), ("Dec-22", "2022-12"), ("Dec 2012", "2012-12"),
    ("Jun-23", "2023-06"), ("June-2023", "2023-06"), ("2023", "2023-03"),
    ("2010", "2010-03"), ("FY23", "2023-03"), ("FY2023", "2023-03"),
    ("fy23", "2023-03"), ("2023-03", "2023-03"), ("2019-12", "2019-12"),
    ("Mar 2014", "2014-03"), ("mar-23", "2023-03"), ("Sep-21", "2021-09"),
    ("Sept-21", "2021-09"), ("Oct 2020", "2020-10"), ("  Mar-23  ", "2023-03"),
    ("Mar   2014", "2014-03"),
])
def test_normalize_year_valid(raw, expected):
    assert normalize_year(raw) == expected


@pytest.mark.parametrize("raw", [
    "garbage", "xyz", "", None, "13th Month 2023", "2023/03", "Q1-2023", "N/A",
    "TTM", "2024.5", "Mar 2016 9m", "Mar 2023 15",
])
def test_normalize_year_invalid(raw):
    assert normalize_year(raw) is None


@pytest.mark.parametrize("raw, expected", [
    ("TCS", "TCS"), ("tcs", "TCS"), (" TCS ", "TCS"), ("BAJAJ-AUTO", "BAJAJ-AUTO"),
    ("bajaj-auto", "BAJAJ-AUTO"), ("M&M", "M&M"), ("m&m", "M&M"),
    ("HDFCBANK", "HDFCBANK"), ("ADANIENSOL", "ADANIENSOL"), ("TATACONSUM", "TATACONSUM"),
    ("AB", "AB"), ("ABCDEFGHIJKL", "ABCDEFGHIJKL"), ("  m&m  ", "M&M"),
    ("Icicibank", "ICICIBANK"), ("heromoto", "HEROMOTO"),
])
def test_normalize_ticker_valid(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", [
    None, "", "   ", "A", "ABCDEFGHIJKLM", "NAN", "TCS/LTD", "TCS LTD",
])
def test_normalize_ticker_invalid(raw):
    assert normalize_ticker(raw) is None