-- ============================================
-- ETL PROCEDURES: SQL transforms for n8n
-- ============================================

-- Procedure to populate dim_date (call once to generate date range)
CREATE OR REPLACE FUNCTION populate_dim_date(start_date DATE, end_date DATE)
RETURNS VOID AS $$
DECLARE
    curr_date DATE := start_date;
BEGIN
    WHILE curr_date <= end_date LOOP
        INSERT INTO dim_date (
            date_key,
            full_date,
            year,
            quarter,
            month,
            month_name,
            week_of_year,
            day_of_month,
            day_of_week,
            day_name,
            is_weekend,
            fiscal_year,
            fiscal_quarter
        ) VALUES (
            TO_CHAR(curr_date, 'YYYYMMDD')::INTEGER,
            curr_date,
            EXTRACT(YEAR FROM curr_date),
            EXTRACT(QUARTER FROM curr_date),
            EXTRACT(MONTH FROM curr_date),
            TO_CHAR(curr_date, 'Month'),
            EXTRACT(WEEK FROM curr_date),
            EXTRACT(DAY FROM curr_date),
            EXTRACT(DOW FROM curr_date),
            TO_CHAR(curr_date, 'Day'),
            EXTRACT(DOW FROM curr_date) IN (0, 6),
            EXTRACT(YEAR FROM curr_date),
            EXTRACT(QUARTER FROM curr_date)
        ) ON CONFLICT (date_key) DO NOTHING;
        
        curr_date := curr_date + INTERVAL '1 day';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Initialize date dimension (2010-2015 to cover the dataset)
SELECT populate_dim_date('2010-01-01'::DATE, '2015-12-31'::DATE);

-- ============================================
-- VIEW: Transform raw to staging (for reference)
-- ============================================
CREATE OR REPLACE VIEW v_stg_transform AS
SELECT 
    invoice_no,
    stock_code,
    COALESCE(NULLIF(TRIM(description), ''), 'Unknown') as description,
    quantity,
    invoice_date,
    unit_price,
    CASE 
        WHEN customer_id IS NULL OR customer_id = '' THEN NULL
        ELSE CAST(customer_id AS INTEGER)
    END as customer_id,
    COALESCE(NULLIF(TRIM(country), ''), 'Unknown') as country,
    ROUND(quantity * unit_price, 2) as line_total,
    CASE WHEN invoice_no LIKE 'C%' THEN TRUE ELSE FALSE END as is_cancelled,
    CASE WHEN quantity < 0 THEN TRUE ELSE FALSE END as is_return
FROM raw_transactions
WHERE 
    invoice_no IS NOT NULL
    AND stock_code IS NOT NULL
    AND invoice_date IS NOT NULL
    AND unit_price IS NOT NULL
    AND unit_price > 0
    AND quantity != 0;

-- ============================================
-- REFRESH FUNCTIONS
-- ============================================

-- Function to refresh staging from raw
CREATE OR REPLACE FUNCTION refresh_staging()
RETURNS INTEGER AS $$
DECLARE
    rows_inserted INTEGER;
BEGIN
    -- Clear and reload staging
    TRUNCATE TABLE stg_transactions_clean;
    
    INSERT INTO stg_transactions_clean (
        invoice_no, stock_code, description, quantity, 
        invoice_date, unit_price, customer_id, country,
        line_total, is_cancelled, is_return
    )
    SELECT 
        invoice_no,
        stock_code,
        COALESCE(NULLIF(TRIM(description), ''), 'Unknown'),
        quantity,
        invoice_date,
        unit_price,
        CASE 
            WHEN customer_id IS NULL OR customer_id = '' THEN NULL
            ELSE CAST(customer_id AS INTEGER)
        END,
        COALESCE(NULLIF(TRIM(country), ''), 'Unknown'),
        ROUND(quantity * unit_price, 2),
        CASE WHEN invoice_no LIKE 'C%' THEN TRUE ELSE FALSE END,
        CASE WHEN quantity < 0 THEN TRUE ELSE FALSE END
    FROM raw_transactions
    WHERE 
        invoice_no IS NOT NULL
        AND stock_code IS NOT NULL
        AND invoice_date IS NOT NULL
        AND unit_price IS NOT NULL
        AND unit_price > 0
        AND quantity != 0;
    
    GET DIAGNOSTICS rows_inserted = ROW_COUNT;
    RETURN rows_inserted;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh dim_country
CREATE OR REPLACE FUNCTION refresh_dim_country()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    INSERT INTO dim_country (country_name)
    SELECT DISTINCT country
    FROM stg_transactions_clean
    WHERE country NOT IN (SELECT country_name FROM dim_country)
    ON CONFLICT (country_name) DO NOTHING;
    
    -- Update aggregates
    UPDATE dim_country dc
    SET 
        total_customers = sub.total_customers,
        total_orders = sub.total_orders,
        total_revenue = sub.total_revenue,
        updated_at = CURRENT_TIMESTAMP
    FROM (
        SELECT 
            country,
            COUNT(DISTINCT customer_id) as total_customers,
            COUNT(DISTINCT invoice_no) as total_orders,
            SUM(CASE WHEN NOT is_cancelled AND NOT is_return THEN line_total ELSE 0 END) as total_revenue
        FROM stg_transactions_clean
        GROUP BY country
    ) sub
    WHERE dc.country_name = sub.country;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh dim_product
CREATE OR REPLACE FUNCTION refresh_dim_product()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    INSERT INTO dim_product (stock_code, description, avg_unit_price)
    SELECT DISTINCT ON (stock_code)
        stock_code,
        description,
        unit_price
    FROM stg_transactions_clean
    WHERE stock_code NOT IN (SELECT stock_code FROM dim_product)
    ORDER BY stock_code, invoice_date DESC
    ON CONFLICT (stock_code) DO NOTHING;
    
    -- Update aggregates
    UPDATE dim_product dp
    SET 
        total_quantity_sold = sub.total_quantity,
        total_revenue = sub.total_revenue,
        avg_unit_price = sub.avg_price,
        first_sold_date = sub.first_sold,
        last_sold_date = sub.last_sold,
        updated_at = CURRENT_TIMESTAMP
    FROM (
        SELECT 
            stock_code,
            SUM(CASE WHEN NOT is_cancelled AND NOT is_return THEN quantity ELSE 0 END) as total_quantity,
            SUM(CASE WHEN NOT is_cancelled AND NOT is_return THEN line_total ELSE 0 END) as total_revenue,
            AVG(unit_price) as avg_price,
            MIN(invoice_date::DATE) as first_sold,
            MAX(invoice_date::DATE) as last_sold
        FROM stg_transactions_clean
        GROUP BY stock_code
    ) sub
    WHERE dp.stock_code = sub.stock_code;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh dim_customer
CREATE OR REPLACE FUNCTION refresh_dim_customer()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    INSERT INTO dim_customer (customer_id)
    SELECT DISTINCT customer_id
    FROM stg_transactions_clean
    WHERE customer_id IS NOT NULL
    AND customer_id NOT IN (SELECT customer_id FROM dim_customer WHERE customer_id IS NOT NULL)
    ON CONFLICT (customer_id) DO NOTHING;
    
    -- Update aggregates
    UPDATE dim_customer dc
    SET 
        first_purchase_date = sub.first_purchase,
        last_purchase_date = sub.last_purchase,
        total_orders = sub.total_orders,
        total_revenue = sub.total_revenue,
        avg_order_value = CASE WHEN sub.total_orders > 0 THEN sub.total_revenue / sub.total_orders ELSE 0 END,
        updated_at = CURRENT_TIMESTAMP
    FROM (
        SELECT 
            customer_id,
            MIN(invoice_date::DATE) as first_purchase,
            MAX(invoice_date::DATE) as last_purchase,
            COUNT(DISTINCT invoice_no) as total_orders,
            SUM(CASE WHEN NOT is_cancelled AND NOT is_return THEN line_total ELSE 0 END) as total_revenue
        FROM stg_transactions_clean
        WHERE customer_id IS NOT NULL
        GROUP BY customer_id
    ) sub
    WHERE dc.customer_id = sub.customer_id;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh fact_sales
CREATE OR REPLACE FUNCTION refresh_fact_sales()
RETURNS INTEGER AS $$
DECLARE
    rows_inserted INTEGER;
BEGIN
    TRUNCATE TABLE fact_sales;
    
    INSERT INTO fact_sales (
        date_key, customer_key, product_key, country_key,
        invoice_no, quantity, unit_price, line_total,
        is_cancelled, is_return
    )
    SELECT 
        TO_CHAR(stg.invoice_date, 'YYYYMMDD')::INTEGER as date_key,
        dc.customer_key,
        dp.product_key,
        dco.country_key,
        stg.invoice_no,
        stg.quantity,
        stg.unit_price,
        stg.line_total,
        stg.is_cancelled,
        stg.is_return
    FROM stg_transactions_clean stg
    LEFT JOIN dim_customer dc ON stg.customer_id = dc.customer_id
    JOIN dim_product dp ON stg.stock_code = dp.stock_code
    JOIN dim_country dco ON stg.country = dco.country_name
    JOIN dim_date dd ON TO_CHAR(stg.invoice_date, 'YYYYMMDD')::INTEGER = dd.date_key;
    
    GET DIAGNOSTICS rows_inserted = ROW_COUNT;
    RETURN rows_inserted;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh mart_daily_kpis
CREATE OR REPLACE FUNCTION refresh_mart_daily_kpis()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    TRUNCATE TABLE mart_daily_kpis;
    
    INSERT INTO mart_daily_kpis (
        date_key, full_date, total_revenue, total_orders, total_items_sold,
        unique_customers, avg_order_value, cancelled_orders, cancelled_revenue,
        return_orders, return_revenue, cancellation_rate, return_rate
    )
    SELECT 
        fs.date_key,
        dd.full_date,
        SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) as total_revenue,
        COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END) as total_orders,
        SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.quantity ELSE 0 END) as total_items_sold,
        COUNT(DISTINCT fs.customer_key) as unique_customers,
        CASE 
            WHEN COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END) > 0 
            THEN SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) / 
                 COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END)
            ELSE 0 
        END as avg_order_value,
        COUNT(DISTINCT CASE WHEN fs.is_cancelled THEN fs.invoice_no END) as cancelled_orders,
        ABS(SUM(CASE WHEN fs.is_cancelled THEN fs.line_total ELSE 0 END)) as cancelled_revenue,
        COUNT(DISTINCT CASE WHEN fs.is_return THEN fs.invoice_no END) as return_orders,
        ABS(SUM(CASE WHEN fs.is_return THEN fs.line_total ELSE 0 END)) as return_revenue,
        CASE 
            WHEN COUNT(DISTINCT fs.invoice_no) > 0 
            THEN COUNT(DISTINCT CASE WHEN fs.is_cancelled THEN fs.invoice_no END)::DECIMAL / COUNT(DISTINCT fs.invoice_no)
            ELSE 0 
        END as cancellation_rate,
        CASE 
            WHEN COUNT(DISTINCT fs.invoice_no) > 0 
            THEN COUNT(DISTINCT CASE WHEN fs.is_return THEN fs.invoice_no END)::DECIMAL / COUNT(DISTINCT fs.invoice_no)
            ELSE 0 
        END as return_rate
    FROM fact_sales fs
    JOIN dim_date dd ON fs.date_key = dd.date_key
    GROUP BY fs.date_key, dd.full_date
    ORDER BY dd.full_date;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh mart_rfm
CREATE OR REPLACE FUNCTION refresh_mart_rfm()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
    max_date DATE;
BEGIN
    -- Get the max date from transactions
    SELECT MAX(full_date) INTO max_date FROM mart_daily_kpis;
    
    TRUNCATE TABLE mart_rfm;
    
    INSERT INTO mart_rfm (
        customer_id, recency_days, frequency, monetary,
        r_score, f_score, m_score, rfm_score, rfm_segment, segment_description
    )
    WITH customer_metrics AS (
        SELECT 
            dc.customer_id,
            (max_date - MAX(dd.full_date)) as recency_days,
            COUNT(DISTINCT fs.invoice_no) as frequency,
            SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) as monetary
        FROM fact_sales fs
        JOIN dim_customer dc ON fs.customer_key = dc.customer_key
        JOIN dim_date dd ON fs.date_key = dd.date_key
        WHERE dc.customer_id IS NOT NULL
        AND NOT fs.is_cancelled
        GROUP BY dc.customer_id
    ),
    rfm_scores AS (
        SELECT 
            customer_id,
            recency_days,
            frequency,
            monetary,
            NTILE(5) OVER (ORDER BY recency_days DESC) as r_score,
            NTILE(5) OVER (ORDER BY frequency ASC) as f_score,
            NTILE(5) OVER (ORDER BY monetary ASC) as m_score
        FROM customer_metrics
        WHERE monetary > 0
    )
    SELECT 
        customer_id,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        CONCAT(r_score, f_score, m_score) as rfm_score,
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 4 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent Customers'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Potential Loyalists'
            WHEN r_score >= 3 AND f_score >= 1 AND m_score >= 2 THEN 'Promising'
            WHEN r_score >= 2 AND r_score <= 3 AND f_score <= 2 AND m_score <= 2 THEN 'Needs Attention'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'Cant Lose Them'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
            ELSE 'Others'
        END as rfm_segment,
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Best customers, high value and engagement'
            WHEN r_score >= 4 AND f_score >= 3 AND m_score >= 3 THEN 'Consistent buyers, respond to promotions'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'New buyers, need nurturing'
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Recent with potential, offer membership'
            WHEN r_score >= 3 AND f_score >= 1 AND m_score >= 2 THEN 'Recent but low frequency, engage more'
            WHEN r_score >= 2 AND r_score <= 3 AND f_score <= 2 AND m_score <= 2 THEN 'Above average but declining'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'Used to be active, reactivation needed'
            WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'High value at risk, urgent action'
            WHEN r_score <= 2 AND f_score <= 2 THEN 'Low activity, may be lost'
            ELSE 'Requires further analysis'
        END as segment_description
    FROM rfm_scores;
    
    -- Update dim_customer with RFM scores
    UPDATE dim_customer dc
    SET 
        rfm_recency_score = mr.r_score,
        rfm_frequency_score = mr.f_score,
        rfm_monetary_score = mr.m_score,
        rfm_segment = mr.rfm_segment,
        updated_at = CURRENT_TIMESTAMP
    FROM mart_rfm mr
    WHERE dc.customer_id = mr.customer_id;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh mart_country_performance
CREATE OR REPLACE FUNCTION refresh_mart_country_performance()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
    total_rev DECIMAL;
    total_ord INTEGER;
BEGIN
    -- Get totals for percentage calculations
    SELECT 
        SUM(CASE WHEN NOT is_cancelled AND NOT is_return THEN line_total ELSE 0 END),
        COUNT(DISTINCT CASE WHEN NOT is_cancelled THEN invoice_no END)
    INTO total_rev, total_ord
    FROM fact_sales;
    
    TRUNCATE TABLE mart_country_performance;
    
    INSERT INTO mart_country_performance (
        country_key, country_name, total_revenue, total_orders,
        total_customers, avg_order_value, revenue_share_pct, orders_share_pct
    )
    SELECT 
        dco.country_key,
        dco.country_name,
        SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) as total_revenue,
        COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END) as total_orders,
        COUNT(DISTINCT fs.customer_key) as total_customers,
        CASE 
            WHEN COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END) > 0 
            THEN SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) / 
                 COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END)
            ELSE 0 
        END as avg_order_value,
        CASE WHEN total_rev > 0 THEN ROUND(SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) / total_rev * 100, 2) ELSE 0 END,
        CASE WHEN total_ord > 0 THEN ROUND(COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END)::DECIMAL / total_ord * 100, 2) ELSE 0 END
    FROM fact_sales fs
    JOIN dim_country dco ON fs.country_key = dco.country_key
    GROUP BY dco.country_key, dco.country_name;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Function to refresh mart_product_performance
CREATE OR REPLACE FUNCTION refresh_mart_product_performance()
RETURNS INTEGER AS $$
DECLARE
    rows_affected INTEGER;
BEGIN
    TRUNCATE TABLE mart_product_performance;
    
    INSERT INTO mart_product_performance (
        product_key, stock_code, description, product_category,
        total_revenue, total_quantity, total_orders, avg_unit_price,
        revenue_rank, quantity_rank
    )
    SELECT 
        dp.product_key,
        dp.stock_code,
        dp.description,
        dp.product_category,
        SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) as total_revenue,
        SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.quantity ELSE 0 END) as total_quantity,
        COUNT(DISTINCT CASE WHEN NOT fs.is_cancelled THEN fs.invoice_no END) as total_orders,
        AVG(fs.unit_price) as avg_unit_price,
        RANK() OVER (ORDER BY SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.line_total ELSE 0 END) DESC) as revenue_rank,
        RANK() OVER (ORDER BY SUM(CASE WHEN NOT fs.is_cancelled AND NOT fs.is_return THEN fs.quantity ELSE 0 END) DESC) as quantity_rank
    FROM fact_sales fs
    JOIN dim_product dp ON fs.product_key = dp.product_key
    GROUP BY dp.product_key, dp.stock_code, dp.description, dp.product_category;
    
    GET DIAGNOSTICS rows_affected = ROW_COUNT;
    RETURN rows_affected;
END;
$$ LANGUAGE plpgsql;

-- Master ETL function to run all transforms
CREATE OR REPLACE FUNCTION run_full_etl()
RETURNS TABLE (
    step_name VARCHAR,
    rows_affected INTEGER,
    duration_ms BIGINT
) AS $$
DECLARE
    start_time TIMESTAMP;
    step_start TIMESTAMP;
    rows_count INTEGER;
BEGIN
    start_time := clock_timestamp();
    
    -- Step 1: Refresh staging
    step_start := clock_timestamp();
    SELECT refresh_staging() INTO rows_count;
    RETURN QUERY SELECT 'refresh_staging'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    -- Step 2: Refresh dimensions
    step_start := clock_timestamp();
    SELECT refresh_dim_country() INTO rows_count;
    RETURN QUERY SELECT 'refresh_dim_country'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    step_start := clock_timestamp();
    SELECT refresh_dim_product() INTO rows_count;
    RETURN QUERY SELECT 'refresh_dim_product'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    step_start := clock_timestamp();
    SELECT refresh_dim_customer() INTO rows_count;
    RETURN QUERY SELECT 'refresh_dim_customer'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    -- Step 3: Refresh fact table
    step_start := clock_timestamp();
    SELECT refresh_fact_sales() INTO rows_count;
    RETURN QUERY SELECT 'refresh_fact_sales'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    -- Step 4: Refresh marts
    step_start := clock_timestamp();
    SELECT refresh_mart_daily_kpis() INTO rows_count;
    RETURN QUERY SELECT 'refresh_mart_daily_kpis'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    step_start := clock_timestamp();
    SELECT refresh_mart_rfm() INTO rows_count;
    RETURN QUERY SELECT 'refresh_mart_rfm'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    step_start := clock_timestamp();
    SELECT refresh_mart_country_performance() INTO rows_count;
    RETURN QUERY SELECT 'refresh_mart_country_performance'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    step_start := clock_timestamp();
    SELECT refresh_mart_product_performance() INTO rows_count;
    RETURN QUERY SELECT 'refresh_mart_product_performance'::VARCHAR, rows_count, EXTRACT(MILLISECONDS FROM clock_timestamp() - step_start)::BIGINT;
    
    RETURN;
END;
$$ LANGUAGE plpgsql;
