PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY, company_logo TEXT, company_name TEXT NOT NULL,
    chart_link TEXT, about_company TEXT, website TEXT, nse_profile TEXT,
    bse_profile TEXT, face_value REAL, book_value REAL,
    roce_percentage REAL, roe_percentage REAL
);

CREATE TABLE IF NOT EXISTS profitandloss (
    source_id INTEGER, company_id TEXT NOT NULL, year TEXT NOT NULL,
    sales REAL, expenses REAL, operating_profit REAL, opm_percentage REAL,
    other_income REAL, interest REAL, depreciation REAL,
    profit_before_tax REAL, tax_percentage REAL, net_profit REAL,
    eps REAL, dividend_payout REAL,
    PRIMARY KEY (company_id, year), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS balancesheet (
    source_id INTEGER, company_id TEXT NOT NULL, year TEXT NOT NULL,
    equity_capital REAL, reserves REAL, borrowings REAL, other_liabilities REAL,
    total_liabilities REAL, fixed_assets REAL, cwip REAL, investments REAL,
    other_asset REAL, total_assets REAL,
    PRIMARY KEY (company_id, year), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS cashflow (
    source_id INTEGER, company_id TEXT NOT NULL, year TEXT NOT NULL,
    operating_activity REAL, investing_activity REAL, financing_activity REAL,
    net_cash_flow REAL,
    PRIMARY KEY (company_id, year), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS analysis (
    source_id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
    compounded_sales_growth_period INTEGER, compounded_sales_growth_pct REAL,
    compounded_profit_growth_period INTEGER, compounded_profit_growth_pct REAL,
    stock_price_cagr_period INTEGER, stock_price_cagr_pct REAL,
    roe_period INTEGER, roe_pct REAL,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS documents (
    source_id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
    report_year INTEGER NOT NULL, annual_report TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS prosandcons (
    source_id INTEGER PRIMARY KEY, company_id TEXT NOT NULL,
    pros TEXT, cons TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS sectors (
    company_id TEXT PRIMARY KEY, broad_sector TEXT NOT NULL, sub_sector TEXT,
    index_weight_pct REAL, market_cap_category TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS stock_prices (
    source_id INTEGER, company_id TEXT NOT NULL, price_date TEXT NOT NULL,
    open_price REAL, high_price REAL, low_price REAL, close_price REAL,
    volume INTEGER, adjusted_close REAL,
    PRIMARY KEY (company_id, price_date), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS market_cap (
    source_id INTEGER, company_id TEXT NOT NULL, cal_year INTEGER NOT NULL,
    market_cap_crore REAL, enterprise_value_crore REAL, pe_ratio REAL,
    pb_ratio REAL, ev_ebitda REAL, dividend_yield_pct REAL,
    PRIMARY KEY (company_id, cal_year), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS financial_ratios (
    source_id INTEGER, company_id TEXT NOT NULL, year TEXT NOT NULL,
    net_profit_margin_pct REAL, operating_profit_margin_pct REAL,
    return_on_equity_pct REAL, debt_to_equity REAL, interest_coverage REAL,
    asset_turnover REAL, free_cash_flow_cr REAL, capex_cr REAL,
    earnings_per_share REAL, book_value_per_share REAL,
    dividend_payout_ratio_pct REAL, total_debt_cr REAL, cash_from_operations_cr REAL,
    PRIMARY KEY (company_id, year), FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS peer_groups (
    source_id INTEGER PRIMARY KEY, peer_group_name TEXT NOT NULL,
    company_id TEXT NOT NULL, is_benchmark INTEGER,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX IF NOT EXISTS idx_pl_year ON profitandloss(year);
CREATE INDEX IF NOT EXISTS idx_bs_year ON balancesheet(year);
CREATE INDEX IF NOT EXISTS idx_cf_year ON cashflow(year);
CREATE INDEX IF NOT EXISTS idx_ratios_year ON financial_ratios(year);
CREATE INDEX IF NOT EXISTS idx_sectors_broad ON sectors(broad_sector);
CREATE INDEX IF NOT EXISTS idx_peer_group_name ON peer_groups(peer_group_name);
CREATE INDEX IF NOT EXISTS idx_stock_prices_date ON stock_prices(price_date);