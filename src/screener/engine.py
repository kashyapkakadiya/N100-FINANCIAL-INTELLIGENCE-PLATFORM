"""
src/screener/engine.py — Module 3, Days 15-17: Filter Engine, 6 Presets,
Composite Score.

Key design notes:
- build_universe() joins financial_ratios (LATEST P&L year per company,
  using the same get_latest_pl_year logic from Sprint 2 - not a naive
  MAX(year), which silently breaks on the interim balance-sheet snapshot
  issue) with market_cap (latest calendar year) and sectors.
- apply_filters() is generic and operator-driven from screener_config.yaml.
  D/E-based filters automatically exempt the Financials sector per spec.
  ICR: a "Debt Free" company (icr_label == 'Debt Free') always passes any
  min_icr threshold, treated as ICR = infinity.
- Turnaround Watch is NOT a generic filter - it needs revenue_cagr_3yr
  (computed here on the fly from raw P&L, since financial_ratios only
  stores the 5yr window) and a YoY D/E trend check, both multi-year
  comparisons a single-row threshold can't express.
"""

from __future__ import annotations
import sqlite3
import sys
from pathlib import Path
import yaml
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.cagr import compute_cagr_for_window

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
CONFIG_PATH = PROJECT_ROOT / "config" / "screener_config.yaml"


def load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def build_universe(conn=None) -> pd.DataFrame:
    """
    One row per company: latest-year financial_ratios + latest market_cap +
    sector + company name. This IS the screener's working DataFrame.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    fr = pd.read_sql("""
        SELECT f1.* FROM financial_ratios f1
        WHERE net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)

    pl_raw = pd.read_sql("SELECT company_id, year, sales, net_profit, dividend_payout FROM profitandloss", conn)
    mc = pd.read_sql("SELECT company_id, cal_year, market_cap_crore, pe_ratio, pb_ratio, dividend_yield_pct FROM market_cap", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector, sub_sector FROM sectors", conn)
    companies = pd.read_sql("SELECT id, company_name FROM companies", conn)

    universe = fr.merge(pl_raw, on=["company_id", "year"], how="left")
    mc_latest = mc.sort_values("cal_year").groupby("company_id").tail(1)
    universe = universe.merge(mc_latest, on="company_id", how="left")
    universe = universe.merge(sectors, on="company_id", how="left")
    universe = universe.merge(companies, left_on="company_id", right_on="id", how="left")

    if own_conn:
        conn.close()
    return universe


_OPS = {
    ">=": lambda s, v: s >= v,
    "<=": lambda s, v: s <= v,
    ">":  lambda s, v: s > v,
    "<":  lambda s, v: s < v,
    "==": lambda s, v: s == v,
}


def apply_filters(df: pd.DataFrame, filters: dict, config: dict) -> pd.DataFrame:
    """
    filters: {'min_roe': 15, 'max_de': 1.0, ...} - keys must exist in
    config['metrics']. Returns the filtered, composite-score-sorted DataFrame.
    """
    metrics = config["metrics"]
    de_exempt_sector = config.get("de_exempt_sector", "Financials")
    mask = pd.Series(True, index=df.index)

    for key, threshold in filters.items():
        if key not in metrics:
            raise KeyError(f"Unknown filter key '{key}' - not defined in screener_config.yaml metrics")
        col = metrics[key]["column"]
        op = metrics[key]["op"]
        op_fn = _OPS[op]

        if key == "max_de":
            # Financials sector is exempt from a D/E *ceiling* check only -
            # high leverage is structurally normal for banks/NBFCs. This
            # does NOT extend to exact_de (a literal debt-free check): a
            # bank isn't "debt-free" just because its leverage is exempt
            # from the ceiling rule, and blindly exempting it there let
            # HDFCBANK/ICICIBANK/AXISBANK (D/E ~7) pass Debt-Free Blue Chip
            # in initial testing - a real bug, not a spec requirement.
            exempt = df["broad_sector"] == de_exempt_sector
            col_mask = exempt | op_fn(df[col], threshold)
        elif key == "min_icr":
            debt_free = df["icr_label"] == "Debt Free"
            col_mask = debt_free | op_fn(df[col], threshold)
        else:
            col_mask = op_fn(df[col], threshold)

        mask &= col_mask.fillna(False)

    result = df[mask].copy()
    if "composite_quality_score_sector" in result.columns:
        return result.sort_values("composite_quality_score_sector", ascending=False)
    return result.sort_values("composite_quality_score", ascending=False)


def screen_turnaround_watch(universe: pd.DataFrame, conn=None) -> pd.DataFrame:
    """
    Bespoke preset: Revenue CAGR 3yr > 10%, FCF positive in latest year,
    D/E declining year-over-year. Requires raw P&L/BS history, not just the
    single-year snapshot in `universe`.
    """
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    pl = pd.read_sql("SELECT company_id, year, sales FROM profitandloss", conn)
    bs = pd.read_sql("SELECT company_id, year, equity_capital, reserves, borrowings FROM balancesheet", conn)

    qualifying = []
    for cid, row in universe.set_index("company_id").iterrows():
        if row.get("free_cash_flow_cr") is None or row["free_cash_flow_cr"] <= 0:
            continue

        sales_series = pl[pl["company_id"] == cid].set_index("year")["sales"].dropna().to_dict()
        cagr_3yr, flag_3yr = compute_cagr_for_window(sales_series, 3)
        if cagr_3yr is None or cagr_3yr <= 10:
            continue

        de_hist = bs[bs["company_id"] == cid].sort_values("year")
        if len(de_hist) < 2:
            continue
        de_hist = de_hist.assign(de=de_hist["borrowings"] / (de_hist["equity_capital"] + de_hist["reserves"]).replace(0, pd.NA))
        de_hist = de_hist.dropna(subset=["de"])
        if len(de_hist) < 2 or de_hist["de"].iloc[-1] >= de_hist["de"].iloc[-2]:
            continue

        qualifying.append(cid)

    if own_conn:
        conn.close()
    return universe[universe["company_id"].isin(qualifying)]


def run_preset(preset_name: str, universe: pd.DataFrame, config: dict, conn=None) -> pd.DataFrame:
    preset = config["presets"][preset_name]
    if preset_name == "turnaround_watch":
        return screen_turnaround_watch(universe, conn)
    return apply_filters(universe, preset["filters"], config)


if __name__ == "__main__":
    config = load_config()
    conn = sqlite3.connect(DB_PATH)
    universe = build_universe(conn)
    print(f"Universe built: {len(universe)} companies")

    for preset_name in config["presets"]:
        result = run_preset(preset_name, universe, config, conn)
        label = config["presets"][preset_name]["label"]
        print(f"\n{label}: {len(result)} companies")
        print(sorted(result["company_id"].tolist())[:10], "..." if len(result) > 10 else "")
    conn.close()