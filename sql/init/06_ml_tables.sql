-- ============================================
-- ML MODEL TRACKING & ENHANCED OUTPUTS
-- ============================================

-- ML Model Runs: Track every training run for reproducibility
CREATE TABLE IF NOT EXISTS ml_model_runs (
    run_id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_type VARCHAR(50) NOT NULL,  -- 'forecast_prophet', 'anomaly_isolation_forest'
    target_metric VARCHAR(50) NOT NULL,  -- 'revenue', 'orders'
    
    -- Training window
    train_start_date DATE NOT NULL,
    train_end_date DATE NOT NULL,
    train_samples INTEGER NOT NULL,
    
    -- Model parameters (JSON for flexibility)
    parameters JSONB NOT NULL DEFAULT '{}',
    
    -- Evaluation metrics
    mape DECIMAL(8,4),  -- Mean Absolute Percentage Error
    smape DECIMAL(8,4), -- Symmetric MAPE
    rmse DECIMAL(14,4), -- Root Mean Square Error
    mae DECIMAL(14,4),  -- Mean Absolute Error
    
    -- Baseline comparison
    baseline_mape DECIMAL(8,4),  -- "Last week = this week" baseline
    baseline_rmse DECIMAL(14,4),
    improvement_vs_baseline_pct DECIMAL(8,4),
    
    -- Model artifacts
    model_version VARCHAR(50),
    code_version VARCHAR(50),
    
    -- Status
    status VARCHAR(20) DEFAULT 'completed',  -- 'running', 'completed', 'failed'
    error_message TEXT,
    
    -- Metadata
    created_by VARCHAR(100) DEFAULT 'ml_service',
    notes TEXT
);

-- ML Backtesting Results: Store individual backtest predictions
CREATE TABLE IF NOT EXISTS ml_backtest_results (
    backtest_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES ml_model_runs(run_id),
    prediction_date DATE NOT NULL,
    actual_value DECIMAL(14,2) NOT NULL,
    predicted_value DECIMAL(14,2) NOT NULL,
    lower_bound DECIMAL(14,2),
    upper_bound DECIMAL(14,2),
    absolute_error DECIMAL(14,2),
    percentage_error DECIMAL(8,4),
    within_confidence_interval BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Enhanced ML Forecasts: Upsert-friendly with run tracking
DROP TABLE IF EXISTS ml_forecast_daily CASCADE;
CREATE TABLE ml_forecast_daily (
    forecast_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    predicted_value DECIMAL(14, 2) NOT NULL,
    lower_bound DECIMAL(14, 2),
    upper_bound DECIMAL(14, 2),
    confidence_level DECIMAL(5,2) DEFAULT 0.95,
    model_run_id INTEGER REFERENCES ml_model_runs(run_id),
    model_name VARCHAR(100),
    model_version VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (forecast_date, metric_name)  -- Natural key for upsert
);

-- Enhanced ML Anomalies: Better anomaly classification with upsert
DROP TABLE IF EXISTS ml_anomalies_daily CASCADE;
CREATE TABLE ml_anomalies_daily (
    anomaly_date DATE NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    actual_value DECIMAL(14, 2) NOT NULL,
    expected_value DECIMAL(14, 2),
    lower_bound DECIMAL(14, 2),
    upper_bound DECIMAL(14, 2),
    deviation_pct DECIMAL(8, 4),
    z_score DECIMAL(8, 4),
    anomaly_type VARCHAR(20),  -- 'spike', 'drop', 'outlier'
    severity VARCHAR(20),  -- 'low', 'medium', 'high', 'critical'
    
    -- Enhanced anomaly context
    is_weekend BOOLEAN DEFAULT FALSE,
    day_of_week INTEGER,
    is_holiday BOOLEAN DEFAULT FALSE,
    seasonality_adjusted BOOLEAN DEFAULT FALSE,
    
    -- Explanation
    probable_cause TEXT,
    business_interpretation TEXT,
    recommended_action TEXT,
    
    -- Alert tracking
    is_alert_sent BOOLEAN DEFAULT FALSE,
    alert_sent_at TIMESTAMP,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMP,
    
    model_run_id INTEGER REFERENCES ml_model_runs(run_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (anomaly_date, metric_name)  -- Natural key for upsert
);

-- View: Active alerts requiring attention
CREATE OR REPLACE VIEW v_active_alerts AS
SELECT 
    anomaly_date,
    metric_name,
    actual_value,
    expected_value,
    deviation_pct,
    severity,
    anomaly_type,
    probable_cause,
    business_interpretation,
    recommended_action,
    CASE 
        WHEN severity = 'critical' THEN 1
        WHEN severity = 'high' THEN 2
        WHEN severity = 'medium' THEN 3
        ELSE 4
    END as priority_order,
    created_at
FROM ml_anomalies_daily
WHERE NOT acknowledged
  AND anomaly_date >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY priority_order, anomaly_date DESC;

-- View: Model performance summary
CREATE OR REPLACE VIEW v_model_performance AS
SELECT 
    model_type,
    target_metric,
    COUNT(*) as total_runs,
    AVG(mape) as avg_mape,
    MIN(mape) as best_mape,
    AVG(improvement_vs_baseline_pct) as avg_improvement_pct,
    MAX(run_timestamp) as last_run
FROM ml_model_runs
WHERE status = 'completed'
GROUP BY model_type, target_metric
ORDER BY model_type, target_metric;

-- View: Forecast vs Actual for dashboard
CREATE OR REPLACE VIEW v_forecast_vs_actual AS
SELECT 
    mdk.full_date,
    mdk.total_revenue as actual_revenue,
    mdk.total_orders as actual_orders,
    fr.predicted_value as forecast_revenue,
    fr.lower_bound as revenue_lower,
    fr.upper_bound as revenue_upper,
    fo.predicted_value as forecast_orders,
    fo.lower_bound as orders_lower,
    fo.upper_bound as orders_upper,
    CASE 
        WHEN fr.predicted_value IS NOT NULL AND mdk.total_revenue > 0 
        THEN ROUND(ABS(mdk.total_revenue - fr.predicted_value) / mdk.total_revenue * 100, 2)
        ELSE NULL
    END as revenue_error_pct,
    CASE 
        WHEN fo.predicted_value IS NOT NULL AND mdk.total_orders > 0 
        THEN ROUND(ABS(mdk.total_orders - fo.predicted_value) / mdk.total_orders * 100, 2)
        ELSE NULL
    END as orders_error_pct,
    trl.last_refresh_at as data_freshness
FROM mart_daily_kpis mdk
LEFT JOIN ml_forecast_daily fr 
    ON mdk.full_date = fr.forecast_date AND fr.metric_name = 'total_revenue'
LEFT JOIN ml_forecast_daily fo 
    ON mdk.full_date = fo.forecast_date AND fo.metric_name = 'total_orders'
LEFT JOIN table_refresh_log trl 
    ON trl.table_name = 'mart_daily_kpis'
ORDER BY mdk.full_date DESC;

-- Indexes for ML tables
CREATE INDEX IF NOT EXISTS idx_ml_runs_type ON ml_model_runs(model_type);
CREATE INDEX IF NOT EXISTS idx_ml_runs_metric ON ml_model_runs(target_metric);
CREATE INDEX IF NOT EXISTS idx_ml_runs_timestamp ON ml_model_runs(run_timestamp);
CREATE INDEX IF NOT EXISTS idx_backtest_run ON ml_backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_forecast_metric ON ml_forecast_daily(metric_name);
CREATE INDEX IF NOT EXISTS idx_anomaly_severity ON ml_anomalies_daily(severity);
CREATE INDEX IF NOT EXISTS idx_anomaly_ack ON ml_anomalies_daily(acknowledged);

COMMENT ON TABLE ml_model_runs IS 'Tracks all ML model training runs with parameters and evaluation metrics';
COMMENT ON TABLE ml_backtest_results IS 'Stores backtest predictions for model evaluation';
COMMENT ON TABLE ml_forecast_daily IS 'Daily forecasts with confidence intervals - upsert-safe';
COMMENT ON TABLE ml_anomalies_daily IS 'Detected anomalies with business context - upsert-safe';
COMMENT ON VIEW v_active_alerts IS 'Unacknowledged anomalies requiring business attention';
COMMENT ON VIEW v_forecast_vs_actual IS 'Combined view of actuals vs forecasts for dashboard';
