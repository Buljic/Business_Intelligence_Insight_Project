-- ============================================
-- STAR SCHEMA: Dimensional Model
-- ============================================

-- DIMENSION: Date
CREATE TABLE IF NOT EXISTS dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    week_of_year INTEGER NOT NULL,
    day_of_month INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    fiscal_year INTEGER,
    fiscal_quarter INTEGER
);

-- DIMENSION: Customer
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id INTEGER UNIQUE,
    first_purchase_date DATE,
    last_purchase_date DATE,
    total_orders INTEGER DEFAULT 0,
    total_revenue DECIMAL(12, 2) DEFAULT 0,
    avg_order_value DECIMAL(10, 2) DEFAULT 0,
    customer_segment VARCHAR(50),
    rfm_recency_score INTEGER,
    rfm_frequency_score INTEGER,
    rfm_monetary_score INTEGER,
    rfm_segment VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DIMENSION: Product
CREATE TABLE IF NOT EXISTS dim_product (
    product_key SERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    product_category VARCHAR(100),
    avg_unit_price DECIMAL(10, 2),
    total_quantity_sold INTEGER DEFAULT 0,
    total_revenue DECIMAL(12, 2) DEFAULT 0,
    first_sold_date DATE,
    last_sold_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DIMENSION: Country/Geography
CREATE TABLE IF NOT EXISTS dim_country (
    country_key SERIAL PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE,
    region VARCHAR(100),
    total_customers INTEGER DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    total_revenue DECIMAL(12, 2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FACT: Sales
CREATE TABLE IF NOT EXISTS fact_sales (
    sales_key SERIAL PRIMARY KEY,
    date_key INTEGER REFERENCES dim_date(date_key),
    customer_key INTEGER REFERENCES dim_customer(customer_key),
    product_key INTEGER REFERENCES dim_product(product_key),
    country_key INTEGER REFERENCES dim_country(country_key),
    invoice_no VARCHAR(20) NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    line_total DECIMAL(12, 2) NOT NULL,
    is_cancelled BOOLEAN DEFAULT FALSE,
    is_return BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for fact table
CREATE INDEX IF NOT EXISTS idx_fact_date_key ON fact_sales(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_customer_key ON fact_sales(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_product_key ON fact_sales(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_country_key ON fact_sales(country_key);
CREATE INDEX IF NOT EXISTS idx_fact_invoice_no ON fact_sales(invoice_no);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_fact_date_country ON fact_sales(date_key, country_key);
CREATE INDEX IF NOT EXISTS idx_fact_date_product ON fact_sales(date_key, product_key);

COMMENT ON TABLE dim_date IS 'Date dimension with calendar attributes';
COMMENT ON TABLE dim_customer IS 'Customer dimension with RFM segmentation';
COMMENT ON TABLE dim_product IS 'Product dimension with aggregated metrics';
COMMENT ON TABLE dim_country IS 'Geographic dimension';
COMMENT ON TABLE fact_sales IS 'Fact table containing sales transactions';
