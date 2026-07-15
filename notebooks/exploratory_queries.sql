-- 1. Row counts for every table
SELECT 'companies' AS tbl, COUNT(*) AS rows FROM companies
UNION ALL SELECT 'profitandloss', COUNT(*) FROM profitandloss
UNION ALL SELECT 'balancesheet', COUNT(*) FROM balancesheet
UNION ALL SELECT 'cashflow', COUNT(*) FROM cashflow
UNION ALL SELECT 'analysis', COUNT(*) FROM analysis
UNION ALL SELECT 'documents', COUNT(*) FROM documents
UNION ALL SELECT 'prosandcons', COUNT(*) FROM prosandcons
UNION ALL SELECT 'sectors', COUNT(*) FROM sectors
UNION ALL SELECT 'stock_prices', COUNT(*) FROM stock_prices
UNION ALL SELECT 'market_cap', COUNT(*) FROM market_cap
UNION ALL SELECT 'financial_ratios', COUNT(*) FROM financial_ratios
UNION ALL SELECT 'peer_groups', COUNT(*) FROM peer_groups;

-- 2. Null audit on key P&L fields
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN sales IS NULL THEN 1 ELSE 0 END) AS null_sales,
       SUM(CASE WHEN net_profit IS NULL THEN 1 ELSE 0 END) AS null_net_profit,
       SUM(CASE WHEN eps IS NULL THEN 1 ELSE 0 END) AS null_eps
FROM profitandloss;

-- 3. Year coverage per company (P&L) — worst 15
SELECT company_id, COUNT(DISTINCT year) AS years_covered,
       MIN(year) AS earliest_year, MAX(year) AS latest_year
FROM profitandloss GROUP BY company_id
ORDER BY years_covered ASC LIMIT 15;

-- 4. Companies below 5-year P&L coverage (DQ-16 candidates)
SELECT company_id, COUNT(DISTINCT year) AS years_covered
FROM profitandloss GROUP BY company_id
HAVING years_covered < 5 ORDER BY years_covered ASC;

-- 5. Companies missing from sectors mapping
SELECT c.id, c.company_name FROM companies c
LEFT JOIN sectors s ON c.id = s.company_id
WHERE s.company_id IS NULL;

-- 6. Sector distribution
SELECT broad_sector, COUNT(*) AS company_count
FROM sectors GROUP BY broad_sector ORDER BY company_count DESC;

-- 7. Balance sheet integrity: assets != liabilities
SELECT company_id, year, total_assets, total_liabilities,
       ROUND(ABS(total_assets - total_liabilities), 2) AS abs_diff
FROM balancesheet
WHERE total_assets != total_liabilities
ORDER BY abs_diff DESC LIMIT 15;

-- 8. Top 10 companies by net_profit, latest year
SELECT p.company_id, c.company_name, p.year, p.net_profit
FROM profitandloss p JOIN companies c ON p.company_id = c.id
WHERE p.year = (SELECT MAX(year) FROM profitandloss)
ORDER BY p.net_profit DESC LIMIT 10;

-- 9. Annual report coverage gaps per company
SELECT c.id, c.company_name, COUNT(d.source_id) AS report_count
FROM companies c LEFT JOIN documents d ON c.id = d.company_id
GROUP BY c.id ORDER BY report_count ASC LIMIT 15;

-- 10. Peer group membership counts (verify all 11 groups populated)
SELECT peer_group_name, COUNT(*) AS member_count,
       SUM(is_benchmark) AS benchmark_count
FROM peer_groups GROUP BY peer_group_name ORDER BY member_count DESC;