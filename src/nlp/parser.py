"""
src/nlp/parser.py — Module 9, Day 29: Analysis Text Parser.

Parses the 4 text fields in analysis.xlsx (compounded_sales_growth,
compounded_profit_growth, stock_price_cagr, roe) using the spec's exact
regex: r'(\d+)\s*Years?:?\s*([\d.]+)%'

IMPORTANT — found during testing against the real data: this regex has
two real limitations that produce genuine parse failures, not garbage:
  1. It requires the period to start with a digit, so 'TTM: 43%' and
     'Last Year: 12%' never match (no leading \d+).
  2. The value group [\d.]+ does NOT include a minus sign, so EVERY
     negative percentage fails to parse (e.g. '1 Year: -2%', '3 Years: -1%'),
     even though '1 Year' matches the period pattern fine.
These are logged to parse_failures.csv exactly as instructed, not silently
patched - see the accompanying chat message for the recommendation to
raise with the team lead about whether the regex should be extended to
capture negative values (a one-character fix: add '-?' before [\d.]+).
"""
from __future__ import annotations
import re
import sqlite3
from pathlib import Path
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output"

PATTERN = re.compile(r"(\d+)\s*Years?:?\s*([\d.]+)%")

METRIC_COLUMNS = {
    "compounded_sales_growth": "compounded_sales_growth",
    "compounded_profit_growth": "compounded_profit_growth",
    "stock_price_cagr": "stock_price_cagr",
    "roe": "roe",
}

CROSS_VALIDATE_MAP = {
    "compounded_sales_growth": "revenue_cagr_5yr",
    "compounded_profit_growth": "pat_cagr_5yr",
}


def parse_analysis_text():
    df = pd.read_excel(RAW_DIR / "analysis.xlsx", sheet_name="Analysis", header=1)

    parsed_rows = []
    failure_rows = []

    for _, row in df.iterrows():
        company_id = str(row["company_id"]).strip().upper()
        for metric_type, col in METRIC_COLUMNS.items():
            raw_text = row[col]
            if pd.isna(raw_text):
                continue
            raw_text = str(raw_text)
            m = PATTERN.search(raw_text)
            if m:
                parsed_rows.append({
                    "company_id": company_id,
                    "metric_type": metric_type,
                    "period_years": int(m.group(1)),
                    "value_pct": float(m.group(2)),
                })
            else:
                failure_rows.append({
                    "company_id": company_id,
                    "metric_type": metric_type,
                    "raw_text": raw_text,
                    "reason": _classify_failure(raw_text),
                })

    parsed_df = pd.DataFrame(parsed_rows)
    failures_df = pd.DataFrame(failure_rows)
    return parsed_df, failures_df


def _classify_failure(raw_text: str) -> str:
    if re.search(r"TTM", raw_text, re.IGNORECASE):
        return "TTM period - no leading digit, regex requires \\d+ Years"
    if re.search(r"Last Year", raw_text, re.IGNORECASE):
        return "'Last Year' text - no leading digit, regex requires \\d+ Years"
    if re.search(r"-\s*[\d.]+%", raw_text):
        return "Negative percentage - regex value group excludes '-'"
    return "Unrecognised format"


def cross_validate(parsed_df):
    conn = sqlite3.connect(DB_PATH)
    ratios = pd.read_sql("""
        SELECT company_id, revenue_cagr_5yr, pat_cagr_5yr FROM financial_ratios f1
        WHERE net_profit_margin_pct IS NOT NULL
        AND year = (SELECT MAX(year) FROM financial_ratios f2
                    WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    """, conn)
    conn.close()

    five_yr = parsed_df[parsed_df["period_years"] == 5].copy()
    rows = []
    for _, row in five_yr.iterrows():
        ratio_col = CROSS_VALIDATE_MAP.get(row["metric_type"])
        if not ratio_col:
            continue
        match = ratios[ratios["company_id"] == row["company_id"]]
        if match.empty or pd.isna(match.iloc[0][ratio_col]):
            continue
        computed = match.iloc[0][ratio_col]
        parsed = row["value_pct"]
        diff = abs(parsed - computed)
        rows.append({
            "company_id": row["company_id"],
            "metric_type": row["metric_type"],
            "parsed_5yr_pct": parsed,
            "ratio_engine_5yr_pct": computed,
            "diff_pts": diff,
            "flagged": diff > 5,
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    parsed_df, failures_df = parse_analysis_text()
    parsed_df.to_csv(OUTPUT_DIR / "analysis_parsed.csv", index=False)
    failures_df.to_csv(OUTPUT_DIR / "parse_failures.csv", index=False)

    print(f"analysis_parsed.csv: {len(parsed_df)} rows parsed")
    print(f"parse_failures.csv: {len(failures_df)} rows failed")
    print()
    print("Failure reasons:")
    print(failures_df["reason"].value_counts())

    cross_val = cross_validate(parsed_df)
    cross_val.to_csv(OUTPUT_DIR / "analysis_cross_validation.csv", index=False)
    print()
    print(f"Cross-validation: {len(cross_val)} 5yr comparisons made, {cross_val['flagged'].sum()} flagged (>5pt divergence)")
    if cross_val["flagged"].any():
        print(cross_val[cross_val["flagged"]].to_string(index=False))