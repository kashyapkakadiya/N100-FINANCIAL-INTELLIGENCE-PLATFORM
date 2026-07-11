# Nifty 100 Financial Intelligence Platform — Sprint 1

Data foundation for a 92-company Nifty 100 analytics platform (Bluestock Fintech internship project).
This sprint builds `nifty100.db` from 12 source Excel files, normalises tickers/years, runs 16 data-quality
rules, and produces a full audit trail.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp config/.env.template .env
```

**Data:** place the 7 core files (`companies.xlsx`, `profitandloss.xlsx`, `balancesheet.xlsx`,
`cashflow.xlsx`, `analysis.xlsx`, `documents.xlsx`, `prosandcons.xlsx`) into `data/raw/`, and the
5 supplementary files (`sectors.xlsx`, `stock_prices.xlsx`, `market_cap.xlsx`, `financial_ratios.xlsx`,
`peer_groups.xlsx`) into `data/supporting/`. These are provided separately and are not committed to
this repo.

## Run

```bash
python src/etl/loader.py     # builds data/nifty100.db, output/load_audit.csv, output/validation_failures.csv
python -m pytest tests/ -v   # 57 unit tests
```

## Structure

| Path | Purpose |
|---|---|
| `src/etl/normaliser.py` | `normalize_year()` / `normalize_ticker()` — pure functions, unit-tested |
| `src/etl/validator.py` | 16 data-quality rule implementations (DQ-01 .. DQ-16) |
| `src/etl/loader.py` | Reads all 12 files, normalises, validates, loads SQLite |
| `db/schema.sql` | 12-table SQLite schema with PK/FK constraints |
| `tests/etl/test_normalise.py` | 57 unit tests |
| `output/load_audit.csv` | Per-table row counts: source / loaded / rejected |
| `output/validation_failures.csv` | Every DQ violation logged with severity |

## Known open item
9 tickers (WIPRO, VEDL, ZOMATO, ULTRACEMCO, UNIONBANK, ZYDUSLIFE, UNITDSPR, VBL, AGTL) have
financial history in the source data but no row in `companies.xlsx`. Currently excluded via
DQ-03 (FK integrity). Pending a decision on whether to add them to the companies master.

## Verify
```bash
python -c "
import sqlite3
conn = sqlite3.connect('data/nifty100.db')
print('companies:', conn.execute('SELECT COUNT(*) FROM companies').fetchone()[0])
print('FK violations:', len(conn.execute('PRAGMA foreign_key_check').fetchall()))
"
```
Expected: `companies: 92`, `FK violations: 0`.