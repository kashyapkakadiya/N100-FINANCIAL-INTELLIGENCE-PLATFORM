# Sprint 3 Retrospective — Screener & Peer Comparison Engine

## Exit Criteria

| Criterion | Status |
|---|---|
| 6 preset screeners, each 5-50 companies | ⚠️ 4/6 in range (Quality Compounder 22, Growth Accelerator 19, Dividend Champion 30, Turnaround Watch 29). Value Pick (2) and Debt-Free Blue Chip (2) below range - genuine data findings, not bugs (see Sprint 3 Day 15-16 notes) |
| peer_comparison.xlsx - exactly 11 sheets | ✅ |
| Peer percentile ranks correct (IT Services, FMCG spot-check) | ✅ verified, top ROE = top percentile in both |
| All DQ rule unit tests pass | ✅ |
| Sprint 3 review signed off | pending team lead review |

## Bugs found and fixed this sprint
1. **Financials D/E exemption misapplied** - the spec's carve-out ("skip
   Financials sector when D/E max filter is applied") was initially coded
   to exempt Financials from BOTH the D/E ceiling check (max_de) and the
   literal debt-free check (exact_de). This let HDFCBANK/ICICIBANK/AXISBANK
   (real D/E ~7) pass the Debt-Free Blue Chip screen. Fixed to exempt only
   max_de - exact_de now correctly requires D/E == 0 for every company.
2. **PERCENT_RANK formula mismatch** - pandas' `.rank(pct=True)` spans
   1/n to 1.0, not SQL's `PERCENT_RANK()` which spans 0.0 to 1.0 exactly
   (the function the spec explicitly names). This meant the best company
   in a peer group never showed a true 100th percentile after D/E
   inversion. Rewrote as `(rank-1)/(n-1)` to match SQL semantics exactly.

## Findings requiring PM input (carried from Day 15-16, still open)
- Value Pick and Debt-Free Blue Chip return only 2 companies each against
  a 5-50 expected range. Root cause confirmed as data characteristics
  (simulated valuation data skews high: mean P/E 44x, mean P/B 7.5x; only
  3/92 companies have exactly zero debt), not implementation bugs.

## Design decisions
- Turnaround Watch required bespoke multi-year logic (3yr CAGR + YoY D/E
  trend) rather than the generic single-snapshot filter engine used by the
  other 5 presets - implemented as a dedicated function.
- Composite score computed in two forms: universe-relative and
  sector-relative (P10/P90 winsorized in both cases). Sector-relative used
  for screener sorting and radar chart "Composite Score" axis.
- Radar chart fallback for the 36 companies with no peer group: same
  8-axis format compared against the full Nifty 100 average, rather than a
  literal "single-metric" chart as worded in the spec - flagged as a
  judgment call favoring information density over literal compliance.

## Deliverables
- output/screener_output.xlsx - 6 sheets, colour-coded
- output/peer_comparison.xlsx - 11 sheets, colour-coded, benchmark highlighted
- reports/radar_charts/ - 92 PNGs
- peer_percentiles table - 560 rows, all 11 groups
- config/screener_config.yaml
- src/screener/engine.py, src/analytics/peer.py, src/analytics/composite_score.py
- src/reports/build_radar_charts.py, src/reports/build_peer_comparison_xlsx.py