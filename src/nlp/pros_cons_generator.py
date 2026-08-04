"""
src/nlp/pros_cons_generator.py — Module 9, Day 30: Auto Pros/Cons Generator.

12 pro rules + 12 con rules, each evaluated per company against its full
history (financial_ratios, profitandloss, balancesheet, cashflow, market_cap).
Only rules with confidence > 60% are included in the output.

CONFIDENCE FORMULA (not specified exactly by the spec, documented here):
- Single-year threshold rules: confidence = min(100, 60 + margin_pct), where
  margin_pct = |actual - threshold| / |threshold| * 100. At exactly the
  threshold, confidence = 60 (the inclusion floor); further past the
  threshold scales up to 100.
- Multi-year trend rules (sustained/improving/declining over N years):
  confidence = min(100, 65 + 5 * extra_qualifying_years_beyond_minimum).

SPEC INCONSISTENCY FLAGGED: Pro Rule 11's title says "Revenue CAGR > PAT
CAGR" but its description says "Revenue growing slower than profits shows
improving operating leverage" - these are opposite conditions. Implemented
using the description's (economically correct) logic: PAT CAGR > Revenue
CAGR indicates operating leverage. The literal title's condition would
flag margin compression as a positive, which doesn't hold up.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

CONFIDENCE_FLOOR = 60


def _threshold_confidence(actual: float, threshold: float) -> float:
    margin_pct = abs(actual - threshold) / max(abs(threshold), 1e-6) * 100
    return min(100.0, 60.0 + margin_pct)


def _trend_confidence(extra_years: int) -> float:
    return min(100.0, 65.0 + 5.0 * extra_years)


class CompanyData:
    def __init__(self, company_id, ratios, pl, bs, cf, market_cap, sector):
        self.company_id = company_id
        self.ratios = ratios.sort_values("year")
        self.pl = pl.sort_values("year")
        self.bs = bs.sort_values("year")
        self.cf = cf.sort_values("year")
        self.market_cap = market_cap.sort_values("cal_year")
        self.sector = sector
        self.latest = ratios.iloc[-1] if len(ratios) else None

    def last_n(self, df, col, n):
        return df[col].dropna().tail(n)


def pro_01_roe_sustained_20(d):
    vals = d.last_n(d.ratios, "return_on_equity_pct", 3)
    if len(vals) < 3 or not (vals > 20).all():
        return None
    extra = int((vals.min() - 20) // 5)
    return _trend_confidence(max(0, extra)), "Consistently high return on equity above 20% demonstrates exceptional capital efficiency"


def pro_02_fcf_positive_5yr(d):
    vals = d.last_n(d.ratios, "free_cash_flow_cr", 5)
    if len(vals) < 5 or not (vals > 0).all():
        return None
    return _trend_confidence(0), "Strong free cash flow generation over 5 years signals healthy business fundamentals"


def pro_03_debt_free(d):
    if d.latest is None or pd.isna(d.latest["debt_to_equity"]) or d.latest["debt_to_equity"] != 0:
        return None
    return 90.0, "Debt-free balance sheet provides financial flexibility and eliminates interest burden"


def pro_04_revenue_cagr_15(d):
    if d.latest is None or pd.isna(d.latest["revenue_cagr_5yr"]) or d.latest["revenue_cagr_5yr"] <= 15:
        return None
    return _threshold_confidence(d.latest["revenue_cagr_5yr"], 15), "Revenue growing at above 15% CAGR over 5 years reflects strong business momentum"


def pro_05_opm_25(d):
    if d.latest is None or pd.isna(d.latest["operating_profit_margin_pct"]) or d.latest["operating_profit_margin_pct"] <= 25:
        return None
    return _threshold_confidence(d.latest["operating_profit_margin_pct"], 25), "Operating profit margin above 25% indicates strong pricing power and cost discipline"


def pro_06_pat_cagr_20(d):
    if d.latest is None or pd.isna(d.latest["pat_cagr_5yr"]) or d.latest["pat_cagr_5yr"] <= 20:
        return None
    return _threshold_confidence(d.latest["pat_cagr_5yr"], 20), "Net profit compounding at above 20% over 5 years creates significant shareholder value"


def pro_07_icr_10_or_debtfree(d):
    if d.latest is None:
        return None
    if d.latest.get("icr_label") == "Debt Free":
        return 95.0, "Very high interest coverage ratio reflects negligible financial stress from debt servicing"
    if pd.notna(d.latest["interest_coverage"]) and d.latest["interest_coverage"] > 10:
        return _threshold_confidence(d.latest["interest_coverage"], 10), "Very high interest coverage ratio reflects negligible financial stress from debt servicing"
    return None


def pro_08_dividend_yield_2_fcf_positive(d):
    if d.latest is None or d.market_cap.empty:
        return None
    latest_yield = d.market_cap["dividend_yield_pct"].dropna()
    if latest_yield.empty:
        return None
    latest_yield = latest_yield.iloc[-1]
    fcf = d.latest.get("free_cash_flow_cr")
    if latest_yield <= 2 or pd.isna(fcf) or fcf <= 0:
        return None
    return _threshold_confidence(latest_yield, 2), "Consistent dividend yield above 2% backed by positive free cash flow"


def pro_09_eps_cagr_15(d):
    if d.latest is None or pd.isna(d.latest["eps_cagr_5yr"]) or d.latest["eps_cagr_5yr"] <= 15:
        return None
    return _threshold_confidence(d.latest["eps_cagr_5yr"], 15), "Earnings per share growing above 15% CAGR indicates strong earnings quality and compounding"


def pro_10_roe_improving_3yr(d):
    vals = d.last_n(d.ratios, "return_on_equity_pct", 3)
    if len(vals) < 3 or not (vals.diff().dropna() > 0).all():
        return None
    return _trend_confidence(1), "Return on equity improving for 3 consecutive years shows strengthening business quality"


def pro_11_operating_leverage(d):
    if d.latest is None or pd.isna(d.latest["pat_cagr_5yr"]) or pd.isna(d.latest["revenue_cagr_5yr"]):
        return None
    if d.latest["pat_cagr_5yr"] <= d.latest["revenue_cagr_5yr"]:
        return None
    gap = d.latest["pat_cagr_5yr"] - d.latest["revenue_cagr_5yr"]
    return min(100.0, 65.0 + gap), "Revenue growing slower than profits shows improving operating leverage and scale benefits"


def pro_12_assets_growing_debt_declining(d):
    if len(d.bs) < 2:
        return None
    last2 = d.bs.tail(2)
    if last2["total_assets"].isna().any() or last2["borrowings"].isna().any():
        return None
    assets_growing = last2["total_assets"].iloc[1] > last2["total_assets"].iloc[0]
    debt_declining = last2["borrowings"].iloc[1] < last2["borrowings"].iloc[0]
    if not (assets_growing and debt_declining):
        return None
    return 75.0, "Growing asset base funded by internal accruals reflects self-sustaining growth"


def con_01_de_high_nonfinancial(d):
    if d.sector == "Financials" or d.latest is None:
        return None
    de = d.latest.get("debt_to_equity")
    if pd.isna(de) or de <= 2.0:
        return None
    return _threshold_confidence(de, 2.0), f"Debt-to-equity ratio of {de:.2f} is elevated for a non-financial company and warrants monitoring"


def con_02_fcf_negative_3yr(d):
    vals = d.last_n(d.ratios, "free_cash_flow_cr", 3)
    if len(vals) < 3 or not (vals < 0).all():
        return None
    return _trend_confidence(0), "Free cash flow negative for 3 consecutive years raises concern about cash generation quality"


def con_03_opm_declining_3yr(d):
    vals = d.last_n(d.ratios, "operating_profit_margin_pct", 3)
    if len(vals) < 3 or not (vals.diff().dropna() < 0).all():
        return None
    return _trend_confidence(0), "Operating margins declining for 3 consecutive years suggest pricing or cost pressure"


def con_04_net_loss_latest(d):
    if d.latest is None:
        return None
    np_ = d.pl[d.pl["year"] == d.latest["year"]]["net_profit"]
    if np_.empty or pd.isna(np_.iloc[0]) or np_.iloc[0] >= 0:
        return None
    return 90.0, "Company reported a net loss in the most recent financial year"


def con_05_revenue_declining_2yr(d):
    vals = d.last_n(d.pl, "sales", 3)
    if len(vals) < 3:
        return None
    diffs = vals.diff().dropna()
    if not (diffs < 0).all():
        return None
    return _trend_confidence(0), "Revenue contraction over 2 consecutive years indicates demand weakness or market share loss"


def con_06_icr_low(d):
    if d.latest is None or d.latest.get("icr_label") == "Debt Free":
        return None
    icr = d.latest.get("interest_coverage")
    if pd.isna(icr) or icr >= 1.5:
        return None
    return _threshold_confidence(icr, 1.5), "Interest coverage ratio below 1.5x indicates the company is at risk of not meeting its debt obligations"


def con_07_dividend_payout_over_100(d):
    if d.latest is None:
        return None
    payout = d.latest.get("dividend_payout_ratio_pct")
    if pd.isna(payout) or payout <= 100:
        return None
    return _threshold_confidence(payout, 100), "Dividend payout ratio above 100% means the company is paying dividends from reserves, which is unsustainable"


def con_08_de_rising_3yr(d):
    vals = d.last_n(d.ratios, "debt_to_equity", 3)
    if len(vals) < 3 or not (vals.diff().dropna() > 0).all():
        return None
    return _trend_confidence(0), "Rising debt-to-equity ratio over 3 years suggests increasing financial leverage risk"


def con_09_eps_declining_3yr(d):
    vals = d.last_n(d.pl, "eps", 3)
    if len(vals) < 3 or not (vals.diff().dropna() < 0).all():
        return None
    return _trend_confidence(0), "Earnings per share declining for 3 consecutive years reflects deteriorating profitability"


def con_10_roce_low(d):
    if d.latest is None:
        return None
    roce = d.latest.get("return_on_capital_employed_pct")
    if pd.isna(roce) or roce >= 10:
        return None
    return _threshold_confidence(roce, 10), "Return on capital employed below 10% suggests the business is not generating sufficient returns on invested capital"


def con_11_net_debt_over_3x_ebitda(d):
    if d.latest is None:
        return None
    net_debt = d.latest.get("net_debt_cr")
    ebitda_proxy = d.pl[d.pl["year"] == d.latest["year"]]["operating_profit"]
    if pd.isna(net_debt) or ebitda_proxy.empty or pd.isna(ebitda_proxy.iloc[0]) or ebitda_proxy.iloc[0] <= 0:
        return None
    ratio = net_debt / ebitda_proxy.iloc[0]
    if ratio <= 3:
        return None
    return _threshold_confidence(ratio, 3), "Net debt exceeding 3 times EBITDA is a high leverage ratio and limits financial flexibility"


def con_12_revenue_cagr_below_5(d):
    if d.latest is None or pd.isna(d.latest["revenue_cagr_5yr"]) or d.latest["revenue_cagr_5yr"] >= 5:
        return None
    return _threshold_confidence(d.latest["revenue_cagr_5yr"], 5), "Revenue growing at below 5% over 5 years lags inflation and suggests limited business momentum"


FRIENDLY_METRIC_NAMES = {
    "return_on_equity_pct": "Return on equity",
    "return_on_capital_employed_pct": "Return on capital employed",
    "net_profit_margin_pct": "Net profit margin",
    "debt_to_equity": "Debt-to-equity ratio",
    "free_cash_flow_cr": "Free cash flow generation",
    "pat_cagr_5yr": "Profit growth (5yr CAGR)",
    "revenue_cagr_5yr": "Revenue growth (5yr CAGR)",
    "eps_cagr_5yr": "EPS growth (5yr CAGR)",
    "interest_coverage": "Interest coverage",
    "asset_turnover": "Asset turnover efficiency",
}


def _universe_percentiles(conn) -> pd.DataFrame:
    """Pooled, universe-wide (all 92) percentile ranks for the same 10
    metrics peer_percentiles uses - fallback for the 36 companies with no
    peer group assigned. Uses the same SQL-standard PERCENT_RANK formula
    as peer.py (not pandas' default rank(pct=True))."""
    ratios = pd.read_sql("""
        SELECT company_id, return_on_equity_pct, return_on_capital_employed_pct,
               net_profit_margin_pct, debt_to_equity, free_cash_flow_cr,
               pat_cagr_5yr, revenue_cagr_5yr, eps_cagr_5yr, interest_coverage, asset_turnover
        FROM financial_ratios f1
        WHERE net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)

    def percent_rank(series):
        n = series.notna().sum()
        if n <= 1:
            return pd.Series([1.0 if pd.notna(v) else None for v in series], index=series.index)
        ranks = series.rank(method="min", ascending=True)
        return (ranks - 1) / (n - 1)

    rows = []
    for metric in FRIENDLY_METRIC_NAMES:
        invert = metric == "debt_to_equity"
        pr = percent_rank(ratios[metric])
        if invert:
            pr = 1 - pr
        for cid, val, p in zip(ratios["company_id"], ratios[metric], pr):
            rows.append({"company_id": cid, "metric": metric, "value": val, "percentile_rank": p})
    return pd.DataFrame(rows)


def generate_fallback_con(conn, company_id: str, peer_percentiles: pd.DataFrame, universe_percentiles: pd.DataFrame):
    """
    For a company with zero rule-triggered cons: find its weakest metric
    relative to peers (or the full universe, if no peer group), and phrase
    it as a factual, data-driven observation rather than a contrived filler
    line. Confidence fixed at 65 - clearly a softer signal than a genuine
    red-flag rule trigger, but real and grounded in actual percentile data.
    """
    company_peer_rows = peer_percentiles[peer_percentiles["company_id"] == company_id]
    source = company_peer_rows if not company_peer_rows.empty else universe_percentiles[universe_percentiles["company_id"] == company_id]
    scope = "its peer group" if not company_peer_rows.empty else "the Nifty 100 universe"

    source = source.dropna(subset=["percentile_rank"])
    if source.empty:
        return None
    weakest = source.loc[source["percentile_rank"].idxmin()]
    metric_name = FRIENDLY_METRIC_NAMES.get(weakest["metric"], weakest["metric"])
    pctile = weakest["percentile_rank"] * 100
    text = f"{metric_name} ranks in the bottom {100 - pctile:.0f}% relative to {scope}, comparatively weaker than the rest of its profile"
    return 65.0, text


def generate_fallback_pro(conn, company_id: str, peer_percentiles: pd.DataFrame, universe_percentiles: pd.DataFrame):
    """Symmetric to generate_fallback_con: strongest relative metric, for
    the small number of companies (BHEL, GODREJCP, JINDALSTEL in testing)
    that trigger zero pro rules."""
    company_peer_rows = peer_percentiles[peer_percentiles["company_id"] == company_id]
    source = company_peer_rows if not company_peer_rows.empty else universe_percentiles[universe_percentiles["company_id"] == company_id]
    scope = "its peer group" if not company_peer_rows.empty else "the Nifty 100 universe"

    source = source.dropna(subset=["percentile_rank"])
    if source.empty:
        return None
    strongest = source.loc[source["percentile_rank"].idxmax()]
    metric_name = FRIENDLY_METRIC_NAMES.get(strongest["metric"], strongest["metric"])
    pctile = strongest["percentile_rank"] * 100
    text = f"{metric_name} ranks in the top {pctile:.0f}% relative to {scope}, a relative strength versus the rest of its profile"
    return 65.0, text


PRO_RULES = [
    ("PRO-01", pro_01_roe_sustained_20), ("PRO-02", pro_02_fcf_positive_5yr),
    ("PRO-03", pro_03_debt_free), ("PRO-04", pro_04_revenue_cagr_15),
    ("PRO-05", pro_05_opm_25), ("PRO-06", pro_06_pat_cagr_20),
    ("PRO-07", pro_07_icr_10_or_debtfree), ("PRO-08", pro_08_dividend_yield_2_fcf_positive),
    ("PRO-09", pro_09_eps_cagr_15), ("PRO-10", pro_10_roe_improving_3yr),
    ("PRO-11", pro_11_operating_leverage), ("PRO-12", pro_12_assets_growing_debt_declining),
]
CON_RULES = [
    ("CON-01", con_01_de_high_nonfinancial), ("CON-02", con_02_fcf_negative_3yr),
    ("CON-03", con_03_opm_declining_3yr), ("CON-04", con_04_net_loss_latest),
    ("CON-05", con_05_revenue_declining_2yr), ("CON-06", con_06_icr_low),
    ("CON-07", con_07_dividend_payout_over_100), ("CON-08", con_08_de_rising_3yr),
    ("CON-09", con_09_eps_declining_3yr), ("CON-10", con_10_roce_low),
    ("CON-11", con_11_net_debt_over_3x_ebitda), ("CON-12", con_12_revenue_cagr_below_5),
]


def load_company_data(conn, company_id):
    ratios = pd.read_sql("SELECT * FROM financial_ratios WHERE company_id = ? AND net_profit_margin_pct IS NOT NULL", conn, params=(company_id,))
    pl = pd.read_sql("SELECT * FROM profitandloss WHERE company_id = ?", conn, params=(company_id,))
    bs = pd.read_sql("SELECT * FROM balancesheet WHERE company_id = ?", conn, params=(company_id,))
    cf = pd.read_sql("SELECT * FROM cashflow WHERE company_id = ?", conn, params=(company_id,))
    mc = pd.read_sql("SELECT * FROM market_cap WHERE company_id = ?", conn, params=(company_id,))
    sector_row = pd.read_sql("SELECT broad_sector FROM sectors WHERE company_id = ?", conn, params=(company_id,))
    sector = sector_row.iloc[0]["broad_sector"] if len(sector_row) else None
    return CompanyData(company_id, ratios, pl, bs, cf, mc, sector)


def generate_all():
    conn = sqlite3.connect(DB_PATH)
    companies = pd.read_sql("SELECT id FROM companies", conn)["id"].tolist()
    peer_percentiles = pd.read_sql("SELECT company_id, metric, percentile_rank FROM peer_percentiles", conn)
    universe_percentiles = _universe_percentiles(conn)

    rows = []
    fallback_used = []
    still_missing = []
    for cid in companies:
        d = load_company_data(conn, cid)
        n_pro, n_con = 0, 0
        for rule_id, fn in PRO_RULES:
            result = fn(d)
            if result:
                confidence, text = result
                if confidence > CONFIDENCE_FLOOR:
                    rows.append({"company_id": cid, "type": "pro", "rule_id": rule_id,
                                 "text": text, "confidence_pct": round(confidence, 1)})
                    n_pro += 1
        for rule_id, fn in CON_RULES:
            result = fn(d)
            if result:
                confidence, text = result
                if confidence > CONFIDENCE_FLOOR:
                    rows.append({"company_id": cid, "type": "con", "rule_id": rule_id,
                                 "text": text, "confidence_pct": round(confidence, 1)})
                    n_con += 1

        if n_pro == 0:
            fb = generate_fallback_pro(conn, cid, peer_percentiles, universe_percentiles)
            if fb:
                confidence, text = fb
                rows.append({"company_id": cid, "type": "pro", "rule_id": "PRO-FALLBACK",
                             "text": text, "confidence_pct": round(confidence, 1)})
                n_pro += 1
                fallback_used.append((cid, "pro"))
        if n_con == 0:
            fb = generate_fallback_con(conn, cid, peer_percentiles, universe_percentiles)
            if fb:
                confidence, text = fb
                rows.append({"company_id": cid, "type": "con", "rule_id": "CON-FALLBACK",
                             "text": text, "confidence_pct": round(confidence, 1)})
                n_con += 1
                fallback_used.append((cid, "con"))

        if n_pro == 0 or n_con == 0:
            still_missing.append((cid, n_pro, n_con))

    conn.close()
    result_df = pd.DataFrame(rows)
    return result_df, fallback_used, still_missing


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result_df, fallback_used, still_missing = generate_all()
    result_df.to_csv(OUTPUT_DIR / "pros_cons_generated.csv", index=False)

    print(f"pros_cons_generated.csv: {len(result_df)} rows")
    print(f"Companies covered: {result_df['company_id'].nunique()} / 92")
    print(f"Pro/con split: {result_df['type'].value_counts().to_dict()}")
    print(f"Fallback (peer/universe percentile) rows used: {len(fallback_used)}")
    print()
    if still_missing:
        print(f"WARNING: {len(still_missing)} companies STILL missing at least 1 pro or 1 con after fallback:")
        for cid, n_pro, n_con in still_missing:
            print(f"  {cid}: {n_pro} pros, {n_con} cons")
    else:
        print("Every company has at least 1 pro and 1 con - exit criterion met.")