# Sprint 1 Retrospective — Data Foundation

## Exit Criteria

| Criterion | Status |
|---|---|
| companies = 92 | ✅ |
| PRAGMA foreign_key_check = 0 | ✅ |
| load_audit.csv — zero CRITICAL rejections | ⚠️ NOT MET — 786 CRITICAL rejections, all root-caused (see below). Not a pipeline bug. |
| 35+ unit tests pass | ✅ 57 passed |
| Manual review: 5 companies correct | ✅ done Day 6, no bugs, 3 coverage gaps found (LODHA, HAL, IRFC) |
| Sprint review signed off | pending team lead read of this doc |

## Data gaps found (source data, not pipeline bugs)

1. **9 orphan tickers** (WIPRO, VEDL, ZOMATO, ULTRACEMCO, UNIONBANK, ZYDUSLIFE,
   UNITDSPR, VBL, AGTL) — financial history exists but no row in companies.xlsx.
   ~425 rows rejected via DQ-03. Decision needed before Sprint 2.
2. **253 duplicate rows** across balancesheet/financial_ratios/cashflow/P&L —
   exact duplicate blocks in source, deduped via DQ-02, kept last occurrence.
3. **108 unparseable year labels** — TTM (rolling, not annual), a bad numeric
   artifact (2024.5), one 9-month stub, one scraping artifact. Rejected via DQ-07.
4. **DIVISLAB has zero rows in documents.xlsx** — confirmed empty at source,
   not a loader issue. Consistent with the project doc's own note that
   documents.xlsx is only ~82% complete.
5. **sectors.xlsx has only 10 of the spec's stated 11 broad sectors** —
   "Conglomerates / Other" (5 companies per spec) is absent from the raw file
   entirely. Confirmed by reading the raw file directly — not a filtering bug.

## Manual review findings (Day 6)
No loader bugs. Balance sheet includes a legitimate interim Sept snapshot
alongside the March annual close. LODHA/HAL/IRFC show cash-flow history
starting years later than P&L/BS — plausible real-world causes. SIEMENS has
a September fiscal year-end, which breaks any query assuming a single global
MAX(year) — confirmed via exploratory query 8. Ratio Engine (Sprint 2) needs
per-company "latest year" logic, not a global one.

## Deliverables
- nifty100.db (12 tables — spec's Sprint 1 task list says 10 but omits
  market_cap, which the Dataset Catalogue requires elsewhere; included all 12)
- output/load_audit.csv, output/validation_failures.csv
- src/etl/{loader.py, validator.py, normaliser.py}
- db/schema.sql
- tests/etl/test_normalise.py — 57 tests
- notebooks/exploratory_queries.sql — 10 queries, verified against live DB
- sprint1_day6_review.md

## Carried into Sprint 2
1. Decision on the 9 orphan tickers
2. Balance sheet join must filter to March-ending periods for annual comparisons
3. Ratio Engine must handle missing years (LODHA/HAL/IRFC) without crashing
4. "Latest year" logic must be per-company, not a single global MAX(year) (SIEMENS)
5. Sector-relative benchmarking (Module 2/6) will only cover 10 of 11 sectors
   until/unless Conglomerates/Other companies are identified and added