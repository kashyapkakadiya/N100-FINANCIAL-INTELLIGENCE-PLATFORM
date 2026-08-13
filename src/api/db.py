"""
src/api/db.py — shared SQLite connection helper for all routers.

Reuses the SAME "latest year" discipline established across this whole
project: never a bare MAX(year) (which picks up the interim
balance-sheet-only snapshot rows first found in Sprint 1/SIEMENS and
re-triggered at least 6 times since) - always
MAX(year) WHERE net_profit_margin_pct IS NOT NULL.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "nifty100.db"

ALL_TABLES = [
    "companies", "profitandloss", "balancesheet", "cashflow", "analysis",
    "documents", "prosandcons", "sectors", "stock_prices", "market_cap",
    "financial_ratios", "peer_groups",
]

LATEST_YEAR_SUBQUERY = """
    year = (SELECT MAX(year) FROM financial_ratios f2
            WHERE f2.company_id = f1.company_id AND f2.net_profit_margin_pct IS NOT NULL)
    AND net_profit_margin_pct IS NOT NULL
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_row_counts() -> dict:
    conn = get_connection()
    counts = {}
    for table in ALL_TABLES:
        try:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            counts[table] = None
    conn.close()
    return counts