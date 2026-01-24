-- ============================================
-- DATA QUALITY & LINEAGE TRACKING
-- ============================================

-- ETL Run Lineage: Track every pipeline execution
CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id SERIAL PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL,  -- 'ingestion', 'etl_full', 'etl_staging', 'ml_pipeline'
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running',  -- 'running', 'success', 'failed', 'warning'
    source_file VARCHAR(255),
    rows_read INTEGER,
    rows_written INTEGER,
    rows_rejected INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Data Quality Checks: Store DQ results for every run
CREATE TABLE IF NOT EXISTS dq_check_results (
    check_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES etl_run_log(run_id),
    check_name VARCHAR(100) NOT NULL,
    check_type VARCHAR(50) NOT NULL,  -- 'row_count', 'null_rate', 'duplicate', 'range', 'referential'
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100),
    expected_value VARCHAR(255),
    actual_value VARCHAR(255),
    threshold DECIMAL(10,4),
    passed BOOLEAN NOT NULL,
    severity VARCHAR(20) DEFAULT 'warning',  -- 'info', 'warning', 'critical'
    message TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data Cleaning Rules: Document all cleaning transformations
CREATE TABLE IF NOT EXISTS data_cleaning_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    source_table VARCHAR(100) NOT NULL,
    target_column VARCHAR(100),
    rule_type VARCHAR(50) NOT NULL,  -- 'filter', 'transform', 'impute', 'flag', 'derive'
    rule_logic TEXT NOT NULL,
    business_justification TEXT NOT NULL,
    impact_description TEXT,
    records_affected_pct DECIMAL(5,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table Refresh Timestamps: Track when each table was last updated
CREATE TABLE IF NOT EXISTS table_refresh_log (
    table_name VARCHAR(100) PRIMARY KEY,
    last_refresh_at TIMESTAMP NOT NULL,
    refresh_run_id INTEGER REFERENCES etl_run_log(run_id),
    row_count INTEGER,
    refresh_duration_ms INTEGER,
    refresh_type VARCHAR(20) DEFAULT 'full'  -- 'full', 'incremental'
);

-- Data Profile Statistics: Store profiling results
CREATE TABLE IF NOT EXISTS data_profile_stats (
    profile_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES etl_run_log(run_id),
    table_name VARCHAR(100) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    total_rows INTEGER,
    null_count INTEGER,
    null_pct DECIMAL(5,2),
    distinct_count INTEGER,
    min_value VARCHAR(255),
    max_value VARCHAR(255),
    mean_value DECIMAL(18,4),
    profiled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- INSERT DATA CLEANING RULES DOCUMENTATION
-- ============================================
INSERT INTO data_cleaning_rules (rule_name, source_table, target_column, rule_type, rule_logic, business_justification, impact_description) VALUES

-- Cancellation Handling
('cancel_flag_invoice', 'raw_transactions', 'is_cancelled', 'flag',
 'CASE WHEN invoice_no LIKE ''C%'' THEN TRUE ELSE FALSE END',
 'Invoices starting with "C" are cancellations in the UK retail system. These represent voided transactions that should not count toward revenue.',
 'Approximately 2% of records. Excluded from revenue/order counts but tracked separately for cancellation rate KPI.'),

-- Return/Negative Quantity Handling  
('return_flag_quantity', 'raw_transactions', 'is_return', 'flag',
 'CASE WHEN quantity < 0 THEN TRUE ELSE FALSE END',
 'Negative quantities indicate product returns. These reduce inventory and revenue and should be tracked separately from sales.',
 'Approximately 2% of records. Line_total becomes negative; tracked in return_rate KPI.'),

-- Zero Quantity Filter
('filter_zero_quantity', 'raw_transactions', 'quantity', 'filter',
 'quantity != 0',
 'Zero-quantity lines have no business meaning - likely data entry errors or system artifacts.',
 'Less than 0.1% of records removed.'),

-- Missing CustomerID Handling
('null_customer_impute', 'raw_transactions', 'customer_id', 'impute',
 'CASE WHEN customer_id IS NULL OR customer_id = '''' THEN NULL ELSE CAST(customer_id AS INTEGER) END',
 'Missing CustomerID indicates anonymous/guest purchases. We preserve these in fact_sales with NULL customer_key but exclude from customer-level analytics (RFM).',
 'Approximately 25% of transactions. Included in aggregate revenue but excluded from customer segmentation.'),

-- Missing Description Handling
('null_description_impute', 'raw_transactions', 'description', 'impute',
 'COALESCE(NULLIF(TRIM(description), ''''), ''Unknown'')',
 'Missing product descriptions are replaced with "Unknown" to maintain referential integrity while flagging data quality issues.',
 'Less than 1% of records. Products still tracked by stock_code.'),

-- Missing Country Handling
('null_country_impute', 'raw_transactions', 'country', 'impute',
 'COALESCE(NULLIF(TRIM(country), ''''), ''Unknown'')',
 'Missing country defaults to "Unknown" to preserve transaction data while flagging geographic data gaps.',
 'Less than 0.01% of records.'),

-- Invalid Price Filter
('filter_invalid_price', 'raw_transactions', 'unit_price', 'filter',
 'unit_price IS NOT NULL AND unit_price > 0',
 'Zero or negative unit prices (outside of returns context) indicate pricing errors or free promotional items that distort revenue metrics.',
 'Less than 0.5% of records removed.'),

-- Line Total Derivation
('derive_line_total', 'raw_transactions', 'line_total', 'derive',
 'ROUND(quantity * unit_price, 2)',
 'Line total is the extended price for each transaction line. Negative for returns/cancellations.',
 'Derived for 100% of valid records.'),

-- Invoice Date Validation
('filter_null_invoice_date', 'raw_transactions', 'invoice_date', 'filter',
 'invoice_date IS NOT NULL',
 'Transactions without dates cannot be placed in time series or date dimensions.',
 'Less than 0.01% of records removed.')

ON CONFLICT (rule_name) DO UPDATE SET 
    updated_at = CURRENT_TIMESTAMP,
    rule_logic = EXCLUDED.rule_logic,
    business_justification = EXCLUDED.business_justification;

-- ============================================
-- DATA QUALITY CHECK FUNCTIONS
-- ============================================

-- Function to run all DQ checks and optionally fail pipeline
CREATE OR REPLACE FUNCTION run_data_quality_checks(p_run_id INTEGER, p_fail_on_critical BOOLEAN DEFAULT TRUE)
RETURNS TABLE (
    check_name VARCHAR,
    passed BOOLEAN,
    severity VARCHAR,
    message TEXT
) AS $$
DECLARE
    v_check_passed BOOLEAN;
    v_actual_value VARCHAR;
    v_has_critical_failure BOOLEAN := FALSE;
BEGIN
    -- ====================================
    -- CHECK 1: Raw table row count
    -- ====================================
    SELECT COUNT(*)::VARCHAR INTO v_actual_value FROM raw_transactions;
    v_check_passed := v_actual_value::INTEGER > 0;
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'raw_row_count', 'row_count', 'raw_transactions', '>0', v_actual_value, v_check_passed, 
            CASE WHEN v_check_passed THEN 'info' ELSE 'critical' END,
            CASE WHEN v_check_passed THEN 'Raw table has ' || v_actual_value || ' rows' ELSE 'CRITICAL: Raw table is empty!' END);
    
    IF NOT v_check_passed THEN v_has_critical_failure := TRUE; END IF;
    RETURN QUERY SELECT 'raw_row_count'::VARCHAR, v_check_passed, 'critical'::VARCHAR, 
                        CASE WHEN v_check_passed THEN 'Passed: ' || v_actual_value || ' rows' ELSE 'FAILED: Empty table' END;

    -- ====================================
    -- CHECK 2: Staging row count vs raw (data loss check)
    -- ====================================
    SELECT ROUND(COUNT(*)::DECIMAL / NULLIF((SELECT COUNT(*) FROM raw_transactions), 0) * 100, 2)::VARCHAR 
    INTO v_actual_value FROM stg_transactions_clean;
    v_check_passed := v_actual_value::DECIMAL >= 85;  -- At least 85% should pass cleaning
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, threshold, passed, severity, message)
    VALUES (p_run_id, 'staging_retention_rate', 'row_count', 'stg_transactions_clean', '>=85%', v_actual_value || '%', 85, v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'warning' END,
            'Staging retains ' || v_actual_value || '% of raw records');
    
    RETURN QUERY SELECT 'staging_retention_rate'::VARCHAR, v_check_passed, 'warning'::VARCHAR, 
                        'Retention: ' || v_actual_value || '%';

    -- ====================================
    -- CHECK 3: Null rate in customer_id (expected ~25%)
    -- ====================================
    SELECT ROUND(COUNT(*) FILTER (WHERE customer_id IS NULL)::DECIMAL / NULLIF(COUNT(*), 0) * 100, 2)::VARCHAR
    INTO v_actual_value FROM stg_transactions_clean;
    v_check_passed := v_actual_value::DECIMAL BETWEEN 15 AND 35;  -- Expected range
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, column_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'customer_id_null_rate', 'null_rate', 'stg_transactions_clean', 'customer_id', '15-35%', v_actual_value || '%', v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'warning' END,
            'CustomerID null rate: ' || v_actual_value || '% (anonymous purchases)');
    
    RETURN QUERY SELECT 'customer_id_null_rate'::VARCHAR, v_check_passed, 'info'::VARCHAR, 
                        'Null rate: ' || v_actual_value || '%';

    -- ====================================
    -- CHECK 4: Duplicate invoice lines
    -- ====================================
    SELECT COUNT(*)::VARCHAR INTO v_actual_value 
    FROM (
        SELECT invoice_no, stock_code, quantity, COUNT(*) 
        FROM stg_transactions_clean 
        GROUP BY invoice_no, stock_code, quantity 
        HAVING COUNT(*) > 1
    ) dupes;
    v_check_passed := v_actual_value::INTEGER < 1000;  -- Some duplicates expected due to data nature
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'duplicate_invoice_lines', 'duplicate', 'stg_transactions_clean', '<1000', v_actual_value, v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'warning' END,
            'Found ' || v_actual_value || ' potential duplicate line groups');
    
    RETURN QUERY SELECT 'duplicate_invoice_lines'::VARCHAR, v_check_passed, 'warning'::VARCHAR, 
                        'Duplicates: ' || v_actual_value;

    -- ====================================
    -- CHECK 5: Mart tables not empty
    -- ====================================
    SELECT COUNT(*)::VARCHAR INTO v_actual_value FROM mart_daily_kpis;
    v_check_passed := v_actual_value::INTEGER > 0;
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'mart_daily_kpis_populated', 'row_count', 'mart_daily_kpis', '>0', v_actual_value, v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'critical' END,
            CASE WHEN v_check_passed THEN 'Daily KPIs mart has ' || v_actual_value || ' days' ELSE 'CRITICAL: Daily KPIs mart is empty!' END);
    
    IF NOT v_check_passed THEN v_has_critical_failure := TRUE; END IF;
    RETURN QUERY SELECT 'mart_daily_kpis_populated'::VARCHAR, v_check_passed, 'critical'::VARCHAR, 
                        CASE WHEN v_check_passed THEN 'Populated: ' || v_actual_value || ' days' ELSE 'FAILED: Empty mart' END;

    -- ====================================
    -- CHECK 6: RFM mart populated
    -- ====================================
    SELECT COUNT(*)::VARCHAR INTO v_actual_value FROM mart_rfm;
    v_check_passed := v_actual_value::INTEGER > 0;
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'mart_rfm_populated', 'row_count', 'mart_rfm', '>0', v_actual_value, v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'critical' END,
            CASE WHEN v_check_passed THEN 'RFM mart has ' || v_actual_value || ' customers' ELSE 'CRITICAL: RFM mart is empty!' END);
    
    IF NOT v_check_passed THEN v_has_critical_failure := TRUE; END IF;
    RETURN QUERY SELECT 'mart_rfm_populated'::VARCHAR, v_check_passed, 'critical'::VARCHAR, 
                        CASE WHEN v_check_passed THEN 'Populated: ' || v_actual_value || ' customers' ELSE 'FAILED: Empty mart' END;

    -- ====================================
    -- CHECK 7: Date range sanity
    -- ====================================
    SELECT MIN(full_date) || ' to ' || MAX(full_date) INTO v_actual_value FROM mart_daily_kpis;
    v_check_passed := v_actual_value IS NOT NULL;
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, column_name, actual_value, passed, severity, message)
    VALUES (p_run_id, 'date_range_check', 'range', 'mart_daily_kpis', 'full_date', v_actual_value, v_check_passed, 'info',
            'Data spans: ' || COALESCE(v_actual_value, 'N/A'));
    
    RETURN QUERY SELECT 'date_range_check'::VARCHAR, v_check_passed, 'info'::VARCHAR, 
                        'Range: ' || COALESCE(v_actual_value, 'N/A');

    -- ====================================
    -- CHECK 8: Referential integrity - fact to dimensions
    -- ====================================
    SELECT COUNT(*)::VARCHAR INTO v_actual_value 
    FROM fact_sales fs 
    WHERE NOT EXISTS (SELECT 1 FROM dim_date dd WHERE dd.date_key = fs.date_key);
    v_check_passed := v_actual_value::INTEGER = 0;
    
    INSERT INTO dq_check_results (run_id, check_name, check_type, table_name, expected_value, actual_value, passed, severity, message)
    VALUES (p_run_id, 'fact_date_integrity', 'referential', 'fact_sales', '0', v_actual_value, v_check_passed,
            CASE WHEN v_check_passed THEN 'info' ELSE 'critical' END,
            v_actual_value || ' fact rows have missing date dimension references');
    
    IF NOT v_check_passed THEN v_has_critical_failure := TRUE; END IF;
    RETURN QUERY SELECT 'fact_date_integrity'::VARCHAR, v_check_passed, 'critical'::VARCHAR, 
                        'Orphans: ' || v_actual_value;

    -- ====================================
    -- FINAL: Update run status based on checks
    -- ====================================
    UPDATE etl_run_log 
    SET status = CASE 
            WHEN v_has_critical_failure THEN 'failed'
            WHEN EXISTS (SELECT 1 FROM dq_check_results WHERE run_id = p_run_id AND NOT passed AND severity = 'warning') THEN 'warning'
            ELSE 'success'
        END,
        completed_at = CURRENT_TIMESTAMP
    WHERE run_id = p_run_id;

    -- Raise exception if critical failure and fail flag is set
    IF v_has_critical_failure AND p_fail_on_critical THEN
        RAISE EXCEPTION 'DATA QUALITY FAILURE: Critical checks failed. Run ID: %', p_run_id;
    END IF;

END;
$$ LANGUAGE plpgsql;

-- ============================================
-- ENHANCED REFRESH FUNCTIONS WITH LINEAGE
-- ============================================

-- Update table refresh log helper
CREATE OR REPLACE FUNCTION log_table_refresh(p_table_name VARCHAR, p_run_id INTEGER, p_row_count INTEGER, p_duration_ms INTEGER)
RETURNS VOID AS $$
BEGIN
    INSERT INTO table_refresh_log (table_name, last_refresh_at, refresh_run_id, row_count, refresh_duration_ms)
    VALUES (p_table_name, CURRENT_TIMESTAMP, p_run_id, p_row_count, p_duration_ms)
    ON CONFLICT (table_name) DO UPDATE SET
        last_refresh_at = CURRENT_TIMESTAMP,
        refresh_run_id = p_run_id,
        row_count = p_row_count,
        refresh_duration_ms = p_duration_ms;
END;
$$ LANGUAGE plpgsql;

-- Enhanced full ETL with lineage and DQ checks
CREATE OR REPLACE FUNCTION run_full_etl_with_dq(p_source_file VARCHAR DEFAULT 'data.csv')
RETURNS TABLE (
    step_name VARCHAR,
    rows_affected INTEGER,
    duration_ms BIGINT,
    status VARCHAR
) AS $$
DECLARE
    v_run_id INTEGER;
    v_start_time TIMESTAMP;
    v_step_start TIMESTAMP;
    v_rows_count INTEGER;
    v_duration BIGINT;
BEGIN
    v_start_time := clock_timestamp();
    
    -- Create ETL run log entry
    INSERT INTO etl_run_log (run_type, source_file, status)
    VALUES ('etl_full', p_source_file, 'running')
    RETURNING run_id INTO v_run_id;
    
    -- Step 1: Refresh staging
    v_step_start := clock_timestamp();
    SELECT refresh_staging() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('stg_transactions_clean', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_staging'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    -- Step 2: Refresh dimensions
    v_step_start := clock_timestamp();
    SELECT refresh_dim_country() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('dim_country', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_dim_country'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    v_step_start := clock_timestamp();
    SELECT refresh_dim_product() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('dim_product', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_dim_product'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    v_step_start := clock_timestamp();
    SELECT refresh_dim_customer() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('dim_customer', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_dim_customer'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    -- Step 3: Refresh fact table
    v_step_start := clock_timestamp();
    SELECT refresh_fact_sales() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('fact_sales', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_fact_sales'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    -- Step 4: Refresh marts
    v_step_start := clock_timestamp();
    SELECT refresh_mart_daily_kpis() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('mart_daily_kpis', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_mart_daily_kpis'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    v_step_start := clock_timestamp();
    SELECT refresh_mart_rfm() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('mart_rfm', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_mart_rfm'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    v_step_start := clock_timestamp();
    SELECT refresh_mart_country_performance() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('mart_country_performance', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_mart_country_performance'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    v_step_start := clock_timestamp();
    SELECT refresh_mart_product_performance() INTO v_rows_count;
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    PERFORM log_table_refresh('mart_product_performance', v_run_id, v_rows_count, v_duration::INTEGER);
    RETURN QUERY SELECT 'refresh_mart_product_performance'::VARCHAR, v_rows_count, v_duration, 'success'::VARCHAR;
    
    -- Step 5: Run data quality checks
    v_step_start := clock_timestamp();
    PERFORM run_data_quality_checks(v_run_id, TRUE);
    v_duration := EXTRACT(MILLISECONDS FROM clock_timestamp() - v_step_start)::BIGINT;
    RETURN QUERY SELECT 'data_quality_checks'::VARCHAR, 
                        (SELECT COUNT(*)::INTEGER FROM dq_check_results WHERE run_id = v_run_id), 
                        v_duration, 
                        (SELECT status FROM etl_run_log WHERE run_id = v_run_id);
    
    -- Update ETL run with summary
    UPDATE etl_run_log 
    SET completed_at = CURRENT_TIMESTAMP,
        rows_written = (SELECT COUNT(*) FROM fact_sales),
        metadata = jsonb_build_object(
            'total_duration_ms', EXTRACT(MILLISECONDS FROM clock_timestamp() - v_start_time),
            'staging_rows', (SELECT COUNT(*) FROM stg_transactions_clean),
            'fact_rows', (SELECT COUNT(*) FROM fact_sales),
            'dq_checks_passed', (SELECT COUNT(*) FROM dq_check_results WHERE run_id = v_run_id AND passed),
            'dq_checks_failed', (SELECT COUNT(*) FROM dq_check_results WHERE run_id = v_run_id AND NOT passed)
        )
    WHERE run_id = v_run_id;
    
    RETURN;

EXCEPTION WHEN OTHERS THEN
    UPDATE etl_run_log 
    SET status = 'failed', 
        completed_at = CURRENT_TIMESTAMP,
        error_message = SQLERRM
    WHERE run_id = v_run_id;
    RAISE;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEW: Dashboard "Last Updated" timestamps
-- ============================================
CREATE OR REPLACE VIEW v_dashboard_freshness AS
SELECT 
    table_name,
    last_refresh_at,
    row_count,
    refresh_duration_ms,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_refresh_at))/3600 AS hours_since_refresh,
    CASE 
        WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '6 hours' THEN 'fresh'
        WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 'stale'
        ELSE 'outdated'
    END AS freshness_status
FROM table_refresh_log
ORDER BY last_refresh_at DESC;

-- ============================================
-- VIEW: Data Quality Summary
-- ============================================
CREATE OR REPLACE VIEW v_dq_summary AS
SELECT 
    erl.run_id,
    erl.run_type,
    erl.started_at,
    erl.completed_at,
    erl.status,
    COUNT(*) FILTER (WHERE dcr.passed) AS checks_passed,
    COUNT(*) FILTER (WHERE NOT dcr.passed) AS checks_failed,
    COUNT(*) FILTER (WHERE NOT dcr.passed AND dcr.severity = 'critical') AS critical_failures
FROM etl_run_log erl
LEFT JOIN dq_check_results dcr ON erl.run_id = dcr.run_id
GROUP BY erl.run_id, erl.run_type, erl.started_at, erl.completed_at, erl.status
ORDER BY erl.started_at DESC;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_etl_run_log_type ON etl_run_log(run_type);
CREATE INDEX IF NOT EXISTS idx_etl_run_log_status ON etl_run_log(status);
CREATE INDEX IF NOT EXISTS idx_dq_check_run ON dq_check_results(run_id);
CREATE INDEX IF NOT EXISTS idx_dq_check_passed ON dq_check_results(passed);

COMMENT ON TABLE etl_run_log IS 'Tracks all ETL pipeline executions for lineage and audit';
COMMENT ON TABLE dq_check_results IS 'Stores data quality check results per ETL run';
COMMENT ON TABLE data_cleaning_rules IS 'Documents all data cleaning/transformation rules with business justification';
COMMENT ON TABLE table_refresh_log IS 'Tracks last refresh time for each table - used for dashboard freshness indicators';
