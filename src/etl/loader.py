"""
loader.py — Module 1: reads all 12 Excel files, normalises, runs the 16 DQ
rules, writes load_audit.csv + validation_failures.csv, loads nifty100.db.
"""

from __future__ import annotations
import logging, re, sqlite3, time
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from etl.normaliser import normalize_ticker, normalize_year
from etl import validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("etl.loader")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SUPPORTING_DIR = PROJECT_ROOT / "data" / "supporting"
OUTPUT_DIR = PROJECT_ROOT / "output"
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_CAGR_PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)\s*%")


def _reject(table, company_id, year, field, issue, raw_value=None, rule_id="DQ-07"):
    return {"rule_id": rule_id, "severity": "CRITICAL", "table": table,
            "company_id": company_id, "year": year, "field": field,
            "issue": issue, "raw_value": raw_value}


def _normalise_company_id_col(df, table, col="company_id"):
    rejects = []
    normed = df[col].apply(normalize_ticker)
    bad_mask = normed.isna()
    for _, row in df[bad_mask].iterrows():
        rejects.append(_reject(table, row[col], row.get("year"), col,
                                "Unparseable/invalid ticker (DQ-08)", row[col], "DQ-08"))
    df = df.copy()
    df[col] = normed
    return df[~bad_mask].reset_index(drop=True), rejects


def _normalise_year_col(df, table, col="year"):
    rejects = []
    normed = df[col].apply(normalize_year)
    bad_mask = normed.isna()
    for _, row in df[bad_mask].iterrows():
        rejects.append(_reject(table, row.get("company_id"), row[col], col,
                                "Unparseable fiscal year label (DQ-07)", row[col], "DQ-07"))
    df = df.copy()
    df[col] = normed
    return df[~bad_mask].reset_index(drop=True), rejects


def _dedup(df, table, keys):
    """DQ-01 (companies PK) / DQ-02 ((company_id, year) PK) — keep last, log every drop."""
    rule_id = "DQ-01" if table == "companies" else "DQ-02"
    dupe_mask = df.duplicated(subset=keys, keep=False)
    drop_mask = df.duplicated(subset=keys, keep="last")
    violations = []
    for _, row in df[drop_mask].iterrows():
        violations.append(_reject(table, row.get("company_id", row.get("id")), row.get("year"),
                                   "+".join(keys),
                                   f"Duplicate {keys} - dropped, kept last ({dupe_mask.sum()} rows share this key)",
                                   None, rule_id))
    df2 = df[~drop_mask].reset_index(drop=True)
    if len(df) != len(df2):
        logger.info(f"{table}: dropped {len(df)-len(df2)} duplicate rows on {keys} ({rule_id})")
    return df2, violations


def _fk_filter(df, table, valid_ids):
    """DQ-03 — reject rows whose company_id isn't in the companies master."""
    mask = df["company_id"].isin(valid_ids)
    rejects = []
    for _, row in df[~mask].iterrows():
        rejects.append(_reject(table, row["company_id"], row.get("year"), "company_id",
                                f"Orphan row - '{row['company_id']}' not in companies master",
                                row["company_id"], "DQ-03"))
    return df[mask].reset_index(drop=True), rejects


def _parse_cagr_cell(raw):
    if pd.isna(raw):
        return (None, None)
    m = _CAGR_PATTERN.search(str(raw))
    return (int(m.group(1)), float(m.group(2))) if m else (None, None)


# ---- per-file loaders ----
def load_companies():
    df = pd.read_excel(RAW_DIR / "companies.xlsx", sheet_name="Companies", header=1)
    df, rej_ticker = _normalise_company_id_col(df, "companies", col="id")
    df["company_name"] = df["company_name"].astype(str).str.replace("\n", " ", regex=False).str.strip()
    df, rej_dedup = _dedup(df, "companies", ["id"])
    return df, rej_ticker + rej_dedup


def load_profitandloss(valid_ids):
    df = pd.read_excel(RAW_DIR / "profitandloss.xlsx", sheet_name="Profit & Loss", header=1)
    df = df.rename(columns={"id": "source_id"})
    df, rej_year = _normalise_year_col(df, "profitandloss")
    df, rej_ticker = _normalise_company_id_col(df, "profitandloss")
    df, rej_fk = _fk_filter(df, "profitandloss", valid_ids)
    df, rej_dedup = _dedup(df, "profitandloss", ["company_id", "year"])
    return df, rej_year + rej_ticker + rej_fk + rej_dedup


def load_balancesheet(valid_ids):
    df = pd.read_excel(RAW_DIR / "balancesheet.xlsx", sheet_name="Balance Sheet", header=1)
    df = df.rename(columns={"id": "source_id"})
    df, rej_year = _normalise_year_col(df, "balancesheet")
    df, rej_ticker = _normalise_company_id_col(df, "balancesheet")
    df, rej_fk = _fk_filter(df, "balancesheet", valid_ids)
    df.loc[df["fixed_assets"] < 0, "fixed_assets"] = 0  # DQ-10
    df, rej_dedup = _dedup(df, "balancesheet", ["company_id", "year"])
    return df, rej_year + rej_ticker + rej_fk + rej_dedup


def load_cashflow(valid_ids):
    df = pd.read_excel(RAW_DIR / "cashflow.xlsx", sheet_name="Cash Flow", header=1)
    df = df.rename(columns={"id": "source_id"})
    df, rej_year = _normalise_year_col(df, "cashflow")
    df, rej_ticker = _normalise_company_id_col(df, "cashflow")
    df, rej_fk = _fk_filter(df, "cashflow", valid_ids)
    df, rej_dedup = _dedup(df, "cashflow", ["company_id", "year"])
    return df, rej_year + rej_ticker + rej_fk + rej_dedup


def load_analysis(valid_ids):
    df = pd.read_excel(RAW_DIR / "analysis.xlsx", sheet_name="Analysis", header=1)
    df = df.rename(columns={"id": "source_id"})
    df, rej_ticker = _normalise_company_id_col(df, "analysis")
    df, rej_fk = _fk_filter(df, "analysis", valid_ids)
    cols = {"compounded_sales_growth": "compounded_sales_growth",
            "compounded_profit_growth": "compounded_profit_growth",
            "stock_price_cagr": "stock_price_cagr", "roe": "roe"}
    for src, prefix in cols.items():
        parsed = df[src].apply(_parse_cagr_cell)
        df[f"{prefix}_period"] = parsed.apply(lambda t: t[0])
        df[f"{prefix}_pct"] = parsed.apply(lambda t: t[1])
    df = df.drop(columns=list(cols.keys()))
    df, rej_dedup = _dedup(df, "analysis", ["source_id"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_documents(valid_ids):
    df = pd.read_excel(RAW_DIR / "documents.xlsx", sheet_name="Documents", header=1)
    df = df.rename(columns={"id": "source_id", "Year": "report_year", "Annual_Report": "annual_report"})
    df, rej_ticker = _normalise_company_id_col(df, "documents")
    df, rej_fk = _fk_filter(df, "documents", valid_ids)
    df, rej_dedup = _dedup(df, "documents", ["source_id"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_prosandcons(valid_ids):
    df = pd.read_excel(RAW_DIR / "prosandcons.xlsx", sheet_name="Pros & Cons", header=1)
    df = df.rename(columns={"id": "source_id"})
    df, rej_ticker = _normalise_company_id_col(df, "prosandcons")
    df, rej_fk = _fk_filter(df, "prosandcons", valid_ids)
    df, rej_dedup = _dedup(df, "prosandcons", ["source_id"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_sectors(valid_ids):
    df = pd.read_excel(SUPPORTING_DIR / "sectors.xlsx", sheet_name="Sheet1", header=0)
    df = df.drop(columns=["id"])
    df, rej_ticker = _normalise_company_id_col(df, "sectors")
    df, rej_fk = _fk_filter(df, "sectors", valid_ids)
    df, rej_dedup = _dedup(df, "sectors", ["company_id"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_stock_prices(valid_ids):
    df = pd.read_excel(SUPPORTING_DIR / "stock_prices.xlsx", sheet_name="Sheet1", header=0)
    df = df.rename(columns={"id": "source_id", "date": "price_date"})
    df, rej_ticker = _normalise_company_id_col(df, "stock_prices")
    df, rej_fk = _fk_filter(df, "stock_prices", valid_ids)
    df, rej_dedup = _dedup(df, "stock_prices", ["company_id", "price_date"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_market_cap(valid_ids):
    df = pd.read_excel(SUPPORTING_DIR / "market_cap.xlsx", sheet_name="Sheet1", header=0)
    df = df.rename(columns={"id": "source_id", "year": "cal_year"})
    df, rej_ticker = _normalise_company_id_col(df, "market_cap")
    df, rej_fk = _fk_filter(df, "market_cap", valid_ids)
    df, rej_dedup = _dedup(df, "market_cap", ["company_id", "cal_year"])
    return df, rej_ticker + rej_fk + rej_dedup


def load_financial_ratios(valid_ids):
    df = pd.read_excel(SUPPORTING_DIR / "financial_ratios.xlsx", sheet_name="Sheet1", header=0)
    df = df.rename(columns={"id": "source_id"})
    df, rej_year = _normalise_year_col(df, "financial_ratios")
    df, rej_ticker = _normalise_company_id_col(df, "financial_ratios")
    df, rej_fk = _fk_filter(df, "financial_ratios", valid_ids)
    df, rej_dedup = _dedup(df, "financial_ratios", ["company_id", "year"])
    return df, rej_year + rej_ticker + rej_fk + rej_dedup


def load_peer_groups(valid_ids):
    df = pd.read_excel(SUPPORTING_DIR / "peer_groups.xlsx", sheet_name="Sheet1", header=0)
    df = df.rename(columns={"id": "source_id"})
    df, rej_ticker = _normalise_company_id_col(df, "peer_groups")
    df, rej_fk = _fk_filter(df, "peer_groups", valid_ids)
    df["is_benchmark"] = df["is_benchmark"].astype(bool).astype(int)
    df, rej_dedup = _dedup(df, "peer_groups", ["source_id"])
    return df, rej_ticker + rej_fk + rej_dedup


def run_pipeline():
    t0 = time.time()
    all_rejects, audit_rows, raw_counts = [], [], {}

    def track(name, path, sheet, header):
        raw_counts[name] = len(pd.read_excel(path, sheet_name=sheet, header=header))

    track("companies", RAW_DIR / "companies.xlsx", "Companies", 1)
    track("profitandloss", RAW_DIR / "profitandloss.xlsx", "Profit & Loss", 1)
    track("balancesheet", RAW_DIR / "balancesheet.xlsx", "Balance Sheet", 1)
    track("cashflow", RAW_DIR / "cashflow.xlsx", "Cash Flow", 1)
    track("analysis", RAW_DIR / "analysis.xlsx", "Analysis", 1)
    track("documents", RAW_DIR / "documents.xlsx", "Documents", 1)
    track("prosandcons", RAW_DIR / "prosandcons.xlsx", "Pros & Cons", 1)
    track("sectors", SUPPORTING_DIR / "sectors.xlsx", "Sheet1", 0)
    track("stock_prices", SUPPORTING_DIR / "stock_prices.xlsx", "Sheet1", 0)
    track("market_cap", SUPPORTING_DIR / "market_cap.xlsx", "Sheet1", 0)
    track("financial_ratios", SUPPORTING_DIR / "financial_ratios.xlsx", "Sheet1", 0)
    track("peer_groups", SUPPORTING_DIR / "peer_groups.xlsx", "Sheet1", 0)

    companies, rej = load_companies()
    all_rejects += rej
    valid_ids = set(companies["id"])
    logger.info(f"companies master: {len(companies)} rows")

    loaders = {"profitandloss": load_profitandloss, "balancesheet": load_balancesheet,
               "cashflow": load_cashflow, "analysis": load_analysis, "documents": load_documents,
               "prosandcons": load_prosandcons, "sectors": load_sectors,
               "stock_prices": load_stock_prices, "market_cap": load_market_cap,
               "financial_ratios": load_financial_ratios, "peer_groups": load_peer_groups}

    tables = {"companies": companies}
    for name, fn in loaders.items():
        df, rej = fn(valid_ids)
        tables[name] = df
        all_rejects += rej
        logger.info(f"Loaded {name}: {len(df)} rows")

    financial_tickers = set(tables["sectors"].loc[tables["sectors"]["broad_sector"] == "Financials", "company_id"])

    violations_df = validator.run_all_checks(tables, financial_tickers, all_rejects)
    violations_df.to_csv(OUTPUT_DIR / "validation_failures.csv", index=False)
    n_crit = int((violations_df["severity"] == "CRITICAL").sum()) if len(violations_df) else 0
    n_warn = int((violations_df["severity"] == "WARNING").sum()) if len(violations_df) else 0
    logger.info(f"DQ results: {n_crit} CRITICAL, {n_warn} WARNING")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())

    for name, df in tables.items():
        df.to_sql(name, conn, if_exists="append", index=False)
        audit_rows.append({"table": name, "rows_in_source": raw_counts.get(name),
                            "rows_loaded": len(df),
                            "rows_rejected": raw_counts.get(name, len(df)) - len(df)})
        logger.info(f"{name}: loaded {len(df)} / {raw_counts.get(name)} source rows")

    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    conn.commit()
    conn.close()

    audit_df = pd.DataFrame(audit_rows)
    audit_df["timestamp"] = pd.Timestamp.now().isoformat()
    audit_df.to_csv(OUTPUT_DIR / "load_audit.csv", index=False)

    logger.info(f"PRAGMA foreign_key_check -> {len(fk_violations)} violations")
    logger.info(f"Runtime: {time.time()-t0:.2f}s")
    return audit_df, violations_df, len(fk_violations)


if __name__ == "__main__":
    audit_df, violations_df, fk_violations = run_pipeline()
    print("\n=== LOAD SUMMARY ===")
    print(audit_df.to_string(index=False))
    print(f"\nFK check violations: {fk_violations}")