-- ============================================
-- BI MARTS: Aggregated tables for reporting
-- ============================================

-- MART: Daily KPIs (used for ML forecasting)
CREATE TABLE IF NOT EXISTS mart_daily_kpis (
    date_key INTEGER PRIMARY KEY REFERENCES dim_date(date_key),
    full_date DATE NOT NULL UNIQUE,
    total_revenue DECIMAL(14, 2) DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    total_items_sold INTEGER DEFAULT 0,
    unique_customers INTEGER DEFAULT 0,
    avg_order_value DECIMAL(10, 2) DEFAULT 0,
    cancelled_orders INTEGER DEFAULT 0,
    cancelled_revenue DECIMAL(12, 2) DEFAULT 0,
    return_orders INTEGER DEFAULT 0,
    return_revenue DECIMAL(12, 2) DEFAULT 0,
    cancellation_rate DECIMAL(5, 4) DEFAULT 0,
    return_rate DECIMAL(5, 4) DEFAULT 0,
    new_customers INTEGER DEFAULT 0,
    repeat_customers INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MART: RFM Segmentation
CREATE TABLE IF NOT EXISTS mart_rfm (
    customer_id INTEGER PRIMARY KEY,
    recency_days INTEGER,
    frequency INTEGER,
    monetary DECIMAL(12, 2),
    r_score INTEGER,
    f_score INTEGER,
    m_score INTEGER,
    rfm_score VARCHAR(10),
    rfm_segment VARCHAR(50),
    segment_description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MART: Country Performance
CREATE TABLE IF NOT EXISTS mart_country_performance (
    country_key INTEGER PRIMARY KEY REFERENCES dim_country(country_key),
    country_name VARCHAR(100) NOT NULL,
    total_revenue DECIMAL(14, 2) DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    total_customers INTEGER DEFAULT 0,
    avg_order_value DECIMAL(10, 2) DEFAULT 0,
    revenue_share_pct DECIMAL(5, 2) DEFAULT 0,
    orders_share_pct DECIMAL(5, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MART: Product Performance
CREATE TABLE IF NOT EXISTS mart_product_performance (
    product_key INTEGER PRIMARY KEY REFERENCES dim_product(product_key),
    stock_code VARCHAR(20) NOT NULL,
    description TEXT,
    product_category VARCHAR(100),
    total_revenue DECIMAL(14, 2) DEFAULT 0,
    total_quantity INTEGER DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    avg_unit_price DECIMAL(10, 2) DEFAULT 0,
    revenue_rank INTEGER,
    quantity_rank INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- MART: Monthly Trends
CREATE TABLE IF NOT EXISTS mart_monthly_trends (
    year_month VARCHAR(7) PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    total_revenue DECIMAL(14, 2) DEFAULT 0,
    total_orders INTEGER DEFAULT 0,
    total_customers INTEGER DEFAULT 0,
    avg_order_value DECIMAL(10, 2) DEFAULT 0,
    revenue_mom_growth DECIMAL(8, 4),
    orders_mom_growth DECIMAL(8, 4),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ML OUTPUT: Forecasts
CREATE TABLE IF NOT EXISTS ml_forecast_daily (
    id SERIAL PRIMARY KEY,
    forecast_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    predicted_value DECIMAL(14, 2) NOT NULL,
    lower_bound DECIMAL(14, 2),
    upper_bound DECIMAL(14, 2),
    model_name VARCHAR(100),
    model_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(forecast_date, metric_name)
);

-- ML OUTPUT: Anomalies
CREATE TABLE IF NOT EXISTS ml_anomalies_daily (
    id SERIAL PRIMARY KEY,
    anomaly_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    actual_value DECIMAL(14, 2) NOT NULL,
    expected_value DECIMAL(14, 2),
    deviation_pct DECIMAL(8, 4),
    anomaly_type VARCHAR(20),
    severity VARCHAR(20),
    is_alert_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for ML tables
CREATE INDEX IF NOT EXISTS idx_forecast_date ON ml_forecast_daily(forecast_date);
CREATE INDEX IF NOT EXISTS idx_forecast_metric ON ml_forecast_daily(metric_name);
CREATE INDEX IF NOT EXISTS idx_anomaly_date ON ml_anomalies_daily(anomaly_date);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON ml_anomalies_daily(severity);

COMMENT ON TABLE mart_daily_kpis IS 'Daily aggregated KPIs for executive dashboards and ML input';
COMMENT ON TABLE mart_rfm IS 'RFM customer segmentation analysis';
COMMENT ON TABLE mart_country_performance IS 'Country-level performance metrics';
COMMENT ON TABLE mart_product_performance IS 'Product-level performance with rankings';
COMMENT ON TABLE mart_monthly_trends IS 'Monthly trend analysis with growth rates';
COMMENT ON TABLE ml_forecast_daily IS 'ML model predictions for daily metrics';
COMMENT ON TABLE ml_anomalies_daily IS 'Detected anomalies in daily metrics';
