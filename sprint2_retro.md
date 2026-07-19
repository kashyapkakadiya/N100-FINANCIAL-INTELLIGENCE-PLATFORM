# Sprint 2 Retrospective — Financial Ratio Engine

## Exit Criteria

| Criterion | Status |
|---|---|
| financial_ratios >= 1,100 rows | ✅ 1,155 |
| All KPI columns populated, zero null-only columns | ✅ |
| 20+ KPI formula unit tests, 0 failures | ✅ 41 passed |
| Manual spot-check (ROE, Revenue CAGR, 3 companies) within 0.1% | ✅ exact match (0.000000 diff) on TCS, SUNPHARMA, BAJFINANCE |
| ratio_edge_cases.log exists, every entry documented | ✅ 43 anomalies, all categorized |
| Sprint review signed off | pending team lead review |

## Critical bug found and fixed during Sprint 2
"Latest year per company" cannot be a naive `MAX(year)` query. Balance sheet
carries a leftover interim snapshot beyond the annual P&L year for most
March-ending companies (traced back to the Sprint 1 finding on SIEMENS).
A naive MAX(year) picked that interim row for nearly every company, silently
nulling ROE/margins and breaking the Day 14 screener test (1 company instead
of 15-50 expected). Fixed by defining "latest year" as the latest year with
a non-null P&L record — implemented as `get_latest_pl_year()` in
`populate_ratios.py`, reusable anywhere downstream needs this pattern
(dashboard, valuation module, pros/cons generator).

## Table collision found and resolved
`financial_ratios.xlsx` (a Sprint 1 supplementary source file) had already
been loaded into a table also named `financial_ratios`. Renamed to
`financial_ratios_source` before the Ratio Engine wrote its own authoritative
version, so no data was silently overwritten or duplicated.

## Edge case log summary (43 anomalies vs companies.xlsx pre-computed values)
- 29 version differences (source value likely a different period/method)
- 11 data source issues, all traced to a single root cause: opm_percentage
  field internally inconsistent with sales/operating_profit for those
  companies (already self-detected by the Day 8 OPM cross-check)
- 2 "extreme capital structure" cases (BEL, HAL) — mathematically correct
  ROCE/ROE, but capital-employed base is unusually thin (PSU dividend policy),
  producing numbers not meaningfully comparable across companies
- 1 formula discrepancy — ROCE/ROE formulas aren't designed for insurance
  company balance sheets (ICICIPRULI); flagged for whoever builds the
  Screener (Module 3) to decide whether to exclude insurers from ROCE-based
  filters entirely rather than re-benchmark them

## Design decisions carried forward
- capital_allocation_label has 121 "Unclassified" rows (CFO/CFI/CFF exactly
  zero) — not covered by the spec's 8 defined sign patterns
- composite_quality_score is a first-pass approximation (winsorized P10/P90
  blend); Module 5 (Health Scoring) should be treated as the authoritative
  version, not this one
- CAGR values are attached only to each company's latest P&L year (one CAGR
  per company, not repeated per row) — ~91-92% null on CAGR columns is
  expected, not a defect

## Deliverables
- financial_ratios table — 1,155 rows, 36 columns
- output/capital_allocation.csv
- output/ratio_edge_cases.log — 43 anomalies, all categorized
- src/analytics/{ratios.py, cagr.py, cashflow_kpis.py, populate_ratios.py}
- tests/kpi/ — 41 unit tests, 0 failures