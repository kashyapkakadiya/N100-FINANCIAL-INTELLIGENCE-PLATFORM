"""
validator.py — implements DQ-01 .. DQ-16 from the project spec.
Each function returns a list of violation dicts. run_all_checks() combines them.
"""

from __future__ import annotations
from typing import Dict, List
import pandas as pd

Violation = Dict[str, object]


def _v(rule_id, severity, table, company_id, year, field, issue, raw_value=None) -> Violation:
    return {"rule_id": rule_id, "severity": severity, "table": table,
            "company_id": company_id, "year": year, "field": field,
            "issue": issue, "raw_value": raw_value}


def dq04_balance_sheet_balance(bs: pd.DataFrame) -> List[Violation]:
    out = []
    valid = bs[(bs["total_assets"].notna()) & (bs["total_assets"] != 0)]
    diff_pct = (valid["total_assets"] - valid["total_liabilities"]).abs() / valid["total_assets"]
    flagged = valid[diff_pct >= 0.01]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-04", "WARNING", "balancesheet", row["company_id"], row["year"],
                       "total_assets/total_liabilities",
                       f"Balance sheet does not balance: assets={row['total_assets']}, "
                       f"liabilities={row['total_liabilities']}"))
    return out


def dq05_opm_cross_check(pl: pd.DataFrame) -> List[Violation]:
    out = []
    valid = pl[(pl["sales"].notna()) & (pl["sales"] != 0) & (pl["opm_percentage"].notna())]
    computed = (valid["operating_profit"] / valid["sales"]) * 100
    diff = (valid["opm_percentage"] - computed).abs()
    flagged = valid[diff > 1.0]
    for idx, row in flagged.iterrows():
        out.append(_v("DQ-05", "WARNING", "profitandloss", row["company_id"], row["year"],
                       "opm_percentage",
                       f"Reported OPM {row['opm_percentage']}% vs computed {computed[idx]:.1f}% (diff > 1.0 pt)"))
    return out


def dq06_positive_sales(pl: pd.DataFrame, financial_tickers: set) -> List[Violation]:
    out = []
    non_fin = pl[~pl["company_id"].isin(financial_tickers)]
    flagged = non_fin[non_fin["sales"] <= 0]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-06", "WARNING", "profitandloss", row["company_id"], row["year"],
                       "sales", f"Non-positive sales ({row['sales']}) for non-financial company", row["sales"]))
    return out


def dq09_net_cash_check(cf: pd.DataFrame) -> List[Violation]:
    out = []
    valid = cf.dropna(subset=["operating_activity", "investing_activity", "financing_activity", "net_cash_flow"])
    computed = valid["operating_activity"] + valid["investing_activity"] + valid["financing_activity"]
    diff = (valid["net_cash_flow"] - computed).abs()
    flagged = valid[diff > 10]
    for idx, row in flagged.iterrows():
        out.append(_v("DQ-09", "WARNING", "cashflow", row["company_id"], row["year"],
                       "net_cash_flow",
                       f"net_cash_flow {row['net_cash_flow']} vs CFO+CFI+CFF {computed[idx]:.1f} (diff > 10 Cr)"))
    return out


def dq10_nonneg_fixed_assets(bs: pd.DataFrame) -> List[Violation]:
    out = []
    flagged = bs[bs["fixed_assets"] < 0]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-10", "WARNING", "balancesheet", row["company_id"], row["year"],
                       "fixed_assets", f"Negative fixed_assets ({row['fixed_assets']}) coerced to 0", row["fixed_assets"]))
    return out


def dq11_tax_rate_range(pl: pd.DataFrame) -> List[Violation]:
    out = []
    valid = pl[pl["tax_percentage"].notna()]
    flagged = valid[(valid["tax_percentage"] < 0) | (valid["tax_percentage"] > 60)]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-11", "WARNING", "profitandloss", row["company_id"], row["year"],
                       "tax_percentage", f"Tax rate {row['tax_percentage']}% outside 0-60% range", row["tax_percentage"]))
    return out


def dq12_dividend_payout_cap(pl: pd.DataFrame) -> List[Violation]:
    out = []
    valid = pl[pl["dividend_payout"].notna()]
    flagged = valid[valid["dividend_payout"] > 200]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-12", "WARNING", "profitandloss", row["company_id"], row["year"],
                       "dividend_payout", f"Dividend payout {row['dividend_payout']}% > 200% cap", row["dividend_payout"]))
    return out


def dq13_url_validity(documents: pd.DataFrame) -> List[Violation]:
    # Network access to bseindia.com isn't available in every environment,
    # so this checks well-formedness (non-null, http/https) rather than a
    # live requests.head() call. Swap in a real HEAD check when you have
    # unrestricted network access.
    out = []
    missing = documents[documents["annual_report"].isna() | (documents["annual_report"] == "")]
    for _, row in missing.iterrows():
        out.append(_v("DQ-13", "WARNING", "documents", row["company_id"], row["report_year"],
                       "annual_report", "Missing annual report URL"))
    malformed = documents[
        documents["annual_report"].notna()
        & ~documents["annual_report"].astype(str).str.startswith(("http://", "https://"))
    ]
    for _, row in malformed.iterrows():
        out.append(_v("DQ-13", "WARNING", "documents", row["company_id"], row["report_year"],
                       "annual_report", "URL does not start with http(s)://", row["annual_report"]))
    return out


def dq14_eps_sign_consistency(pl: pd.DataFrame) -> List[Violation]:
    out = []
    valid = pl.dropna(subset=["eps", "net_profit"])
    flagged = valid[(valid["net_profit"] > 0) & (valid["eps"] <= 0)]
    for _, row in flagged.iterrows():
        out.append(_v("DQ-14", "WARNING", "profitandloss", row["company_id"], row["year"],
                       "eps", f"net_profit={row['net_profit']} > 0 but eps={row['eps']} <= 0"))
    return out


def dq15_strict_balance_info(bs: pd.DataFrame) -> List[Violation]:
    valid = bs.dropna(subset=["total_assets", "total_liabilities"])
    flagged = valid[valid["total_assets"] != valid["total_liabilities"]]
    return [_v("DQ-15", "INFO", "balancesheet", None, None, "total_assets/total_liabilities",
                f"{len(flagged)} of {len(valid)} rows have assets != liabilities exactly "
                f"(informational only; DQ-04 governs the 1% tolerance flag)")]


def dq16_coverage_check(pl, bs, cf) -> List[Violation]:
    out = []
    for name, df in [("profitandloss", pl), ("balancesheet", bs), ("cashflow", cf)]:
        counts = df.groupby("company_id").size()
        short = counts[counts < 5]
        for cid, n in short.items():
            out.append(_v("DQ-16", "WARNING", name, cid, None, "year_coverage",
                           f"Only {n} year(s) of history (< 5yr minimum)"))
    return out


def run_all_checks(tables: Dict[str, pd.DataFrame], financial_tickers: set,
                    pre_normalisation_rejects: List[Violation]) -> pd.DataFrame:
    """
    tables: dict of table_name -> already-normalised, deduped, FK-filtered DataFrame
            (i.e. what will actually be loaded into SQLite).
    pre_normalisation_rejects: DQ-01/02/03/07/08 violations captured by the
            loader BEFORE those rows were dropped (see loader.py).
    """
    violations: List[Violation] = list(pre_normalisation_rejects)
    violations += dq04_balance_sheet_balance(tables["balancesheet"])
    violations += dq05_opm_cross_check(tables["profitandloss"])
    violations += dq06_positive_sales(tables["profitandloss"], financial_tickers)
    violations += dq09_net_cash_check(tables["cashflow"])
    violations += dq10_nonneg_fixed_assets(tables["balancesheet"])
    violations += dq11_tax_rate_range(tables["profitandloss"])
    violations += dq12_dividend_payout_cap(tables["profitandloss"])
    violations += dq13_url_validity(tables["documents"])
    violations += dq14_eps_sign_consistency(tables["profitandloss"])
    violations += dq15_strict_balance_info(tables["balancesheet"])
    violations += dq16_coverage_check(tables["profitandloss"], tables["balancesheet"], tables["cashflow"])

    if not violations:
        return pd.DataFrame(columns=["rule_id", "severity", "table", "company_id", "year", "field", "issue", "raw_value"])
    return pd.DataFrame(violations)