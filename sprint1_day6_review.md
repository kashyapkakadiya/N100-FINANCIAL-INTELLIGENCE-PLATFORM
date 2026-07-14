# Day 6 — Manual Data Quality Review

**Sample reviewed:** SUNPHARMA, BAJFINANCE, ADANIGREEN, HAL, EICHERMOT (random, seed=42)

**Findings:**
1. Balance sheet consistently includes one extra row beyond P&L/CF (interim
   Sept snapshot alongside the annual March close) — confirmed as legitimate
   Screener.in convention, not a loader defect. Affects join logic for
   Ratio Engine (Sprint 2): filter to March-ending periods for annual
   comparisons.
2. HAL shows a 4-year coverage gap between P&L (from 2013) and BS/CF
   (from 2016/2017). Investigated further — not isolated: LODHA (5yr gap,
   CF only) and IRFC (3yr gap, CF only) show the same pattern. Likely
   explanation: cash flow statement disclosure was less consistently
   available in older filings, and IRFC specifically only listed in 2021.
3. JIOFIN has <5 years across all three statements (DQ-16 flag) — expected,
   demerged/listed in 2023.

**Conclusion:** No loader bugs found. All gaps trace to genuine source-data
characteristics, already logged via DQ-16 (coverage) in validation_failures.csv.
Recommendation for Sprint 2: any ratio requiring cash-flow data (FCF, CFO/PAT)
must handle missing years gracefully (return None, not crash) — LODHA/HAL/IRFC
will hit this regardless of which 5 years are queried.