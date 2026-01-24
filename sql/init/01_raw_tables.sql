-- ============================================
-- RAW LAYER: Initial tables for data ingestion
-- ============================================

-- Raw transactions table (landing zone for CSV data)
CREATE TABLE IF NOT EXISTS raw_transactions (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(20),
    stock_code VARCHAR(20),
    description TEXT,
    quantity INTEGER,
    invoice_date TIMESTAMP,
    unit_price DECIMAL(10, 2),
    customer_id VARCHAR(20),
    country VARCHAR(100),
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster querying
CREATE INDEX IF NOT EXISTS idx_raw_invoice_date ON raw_transactions(invoice_date);
CREATE INDEX IF NOT EXISTS idx_raw_customer_id ON raw_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_raw_stock_code ON raw_transactions(stock_code);

-- Staging table for cleaned transactions
CREATE TABLE IF NOT EXISTS stg_transactions_clean (
    id SERIAL PRIMARY KEY,
    invoice_no VARCHAR(20) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    description TEXT,
    quantity INTEGER NOT NULL,
    invoice_date TIMESTAMP NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    customer_id INTEGER,
    country VARCHAR(100) NOT NULL,
    line_total DECIMAL(12, 2),
    is_cancelled BOOLEAN DEFAULT FALSE,
    is_return BOOLEAN DEFAULT FALSE,
    transformed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stg_invoice_date ON stg_transactions_clean(invoice_date);
CREATE INDEX IF NOT EXISTS idx_stg_customer_id ON stg_transactions_clean(customer_id);
CREATE INDEX IF NOT EXISTS idx_stg_stock_code ON stg_transactions_clean(stock_code);
CREATE INDEX IF NOT EXISTS idx_stg_country ON stg_transactions_clean(country);

COMMENT ON TABLE raw_transactions IS 'Raw landing zone for CSV data ingestion';
COMMENT ON TABLE stg_transactions_clean IS 'Cleaned and validated transactions with business rules applied';
