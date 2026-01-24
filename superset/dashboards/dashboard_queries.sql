-- ============================================
-- SUPERSET DASHBOARD QUERIES
-- Use these queries to create charts in Superset
-- ============================================

-- ============================================
-- EXECUTIVE OVERVIEW DASHBOARD
-- ============================================

-- 1. Total Revenue Over Time (Line Chart)
SELECT 
    full_date as "Date",
    total_revenue as "Revenue",
    total_orders as "Orders"
FROM mart_daily_kpis
ORDER BY full_date;

-- 2. Revenue by Country (Pie/Bar Chart)
SELECT 
    country_name as "Country",
    total_revenue as "Revenue",
    revenue_share_pct as "Revenue Share %"
FROM mart_country_performance
ORDER BY total_revenue DESC
LIMIT 10;

-- 3. Monthly Trend Summary (Table)
SELECT 
    TO_CHAR(full_date, 'YYYY-MM') as "Month",
    SUM(total_revenue) as "Revenue",
    SUM(total_orders) as "Orders",
    SUM(unique_customers) as "Customers",
    ROUND(AVG(avg_order_value), 2) as "Avg Order Value"
FROM mart_daily_kpis
GROUP BY TO_CHAR(full_date, 'YYYY-MM')
ORDER BY "Month";

-- 4. KPI Big Numbers
-- Total Revenue
SELECT SUM(total_revenue) as "Total Revenue" FROM mart_daily_kpis;

-- Total Orders
SELECT SUM(total_orders) as "Total Orders" FROM mart_daily_kpis;

-- Unique Customers
SELECT COUNT(DISTINCT customer_id) as "Total Customers" FROM dim_customer WHERE customer_id IS NOT NULL;

-- Average Order Value
SELECT ROUND(AVG(avg_order_value), 2) as "Average Order Value" FROM mart_daily_kpis WHERE avg_order_value > 0;

-- 5. Return & Cancellation Rates (Gauge/Line)
SELECT 
    full_date as "Date",
    ROUND(cancellation_rate * 100, 2) as "Cancellation Rate %",
    ROUND(return_rate * 100, 2) as "Return Rate %"
FROM mart_daily_kpis
ORDER BY full_date;

-- ============================================
-- CUSTOMER VALUE DASHBOARD (RFM)
-- ============================================

-- 1. RFM Segment Distribution (Pie Chart)
SELECT 
    rfm_segment as "Segment",
    COUNT(*) as "Customer Count",
    ROUND(SUM(monetary), 2) as "Total Revenue"
FROM mart_rfm
GROUP BY rfm_segment
ORDER BY "Customer Count" DESC;

-- 2. RFM Segment Details (Table)
SELECT 
    rfm_segment as "Segment",
    segment_description as "Description",
    COUNT(*) as "Customers",
    ROUND(AVG(recency_days), 0) as "Avg Recency (Days)",
    ROUND(AVG(frequency), 1) as "Avg Frequency",
    ROUND(AVG(monetary), 2) as "Avg Monetary"
FROM mart_rfm
GROUP BY rfm_segment, segment_description
ORDER BY "Customers" DESC;

-- 3. RFM Score Heatmap
SELECT 
    r_score as "Recency Score",
    f_score as "Frequency Score",
    COUNT(*) as "Customer Count"
FROM mart_rfm
GROUP BY r_score, f_score
ORDER BY r_score, f_score;

-- 4. Top Customers by Value (Table)
SELECT 
    customer_id as "Customer ID",
    rfm_segment as "Segment",
    recency_days as "Days Since Last Purchase",
    frequency as "Purchase Frequency",
    ROUND(monetary, 2) as "Total Spend"
FROM mart_rfm
ORDER BY monetary DESC
LIMIT 20;

-- ============================================
-- PRODUCT PERFORMANCE DASHBOARD
-- ============================================

-- 1. Top Products by Revenue (Bar Chart)
SELECT 
    stock_code as "SKU",
    LEFT(description, 50) as "Product",
    ROUND(total_revenue, 2) as "Revenue",
    total_quantity as "Quantity Sold"
FROM mart_product_performance
ORDER BY total_revenue DESC
LIMIT 20;

-- 2. Top Products by Quantity (Bar Chart)
SELECT 
    stock_code as "SKU",
    LEFT(description, 50) as "Product",
    total_quantity as "Quantity Sold",
    ROUND(total_revenue, 2) as "Revenue"
FROM mart_product_performance
ORDER BY total_quantity DESC
LIMIT 20;

-- 3. Product Revenue Distribution
SELECT 
    CASE 
        WHEN revenue_rank <= 10 THEN 'Top 10'
        WHEN revenue_rank <= 50 THEN 'Top 11-50'
        WHEN revenue_rank <= 100 THEN 'Top 51-100'
        ELSE 'Others'
    END as "Tier",
    COUNT(*) as "Product Count",
    SUM(total_revenue) as "Total Revenue"
FROM mart_product_performance
GROUP BY 
    CASE 
        WHEN revenue_rank <= 10 THEN 'Top 10'
        WHEN revenue_rank <= 50 THEN 'Top 11-50'
        WHEN revenue_rank <= 100 THEN 'Top 51-100'
        ELSE 'Others'
    END;

-- 4. Daily Product Sales Trend
SELECT 
    dd.full_date as "Date",
    dp.stock_code as "SKU",
    SUM(fs.quantity) as "Quantity",
    SUM(fs.line_total) as "Revenue"
FROM fact_sales fs
JOIN dim_date dd ON fs.date_key = dd.date_key
JOIN dim_product dp ON fs.product_key = dp.product_key
WHERE NOT fs.is_cancelled AND NOT fs.is_return
GROUP BY dd.full_date, dp.stock_code
ORDER BY dd.full_date, "Revenue" DESC;

-- ============================================
-- AI/ML DASHBOARD
-- ============================================

-- 1. Revenue Forecast vs Actual (Line Chart)
SELECT 
    COALESCE(mk.full_date, mf.forecast_date) as "Date",
    mk.total_revenue as "Actual Revenue",
    mf.predicted_value as "Predicted Revenue",
    mf.lower_bound as "Lower Bound",
    mf.upper_bound as "Upper Bound"
FROM mart_daily_kpis mk
FULL OUTER JOIN ml_forecast_daily mf 
    ON mk.full_date = mf.forecast_date AND mf.metric_name = 'total_revenue'
ORDER BY "Date";

-- 2. Orders Forecast vs Actual (Line Chart)
SELECT 
    COALESCE(mk.full_date, mf.forecast_date) as "Date",
    mk.total_orders as "Actual Orders",
    mf.predicted_value as "Predicted Orders",
    mf.lower_bound as "Lower Bound",
    mf.upper_bound as "Upper Bound"
FROM mart_daily_kpis mk
FULL OUTER JOIN ml_forecast_daily mf 
    ON mk.full_date = mf.forecast_date AND mf.metric_name = 'total_orders'
ORDER BY "Date";

-- 3. Detected Anomalies Table
SELECT 
    anomaly_date as "Date",
    metric_name as "Metric",
    ROUND(actual_value, 2) as "Actual",
    ROUND(expected_value, 2) as "Expected",
    ROUND(deviation_pct, 1) as "Deviation %",
    anomaly_type as "Type",
    severity as "Severity"
FROM ml_anomalies_daily
ORDER BY anomaly_date DESC, 
    CASE severity 
        WHEN 'critical' THEN 1 
        WHEN 'high' THEN 2 
        WHEN 'medium' THEN 3 
        ELSE 4 
    END;

-- 4. Anomaly Summary by Severity (Pie Chart)
SELECT 
    severity as "Severity",
    COUNT(*) as "Count"
FROM ml_anomalies_daily
GROUP BY severity
ORDER BY 
    CASE severity 
        WHEN 'critical' THEN 1 
        WHEN 'high' THEN 2 
        WHEN 'medium' THEN 3 
        ELSE 4 
    END;

-- 5. Future Forecasts (Next 7 Days)
SELECT 
    forecast_date as "Date",
    metric_name as "Metric",
    ROUND(predicted_value, 2) as "Predicted",
    ROUND(lower_bound, 2) as "Lower Bound",
    ROUND(upper_bound, 2) as "Upper Bound"
FROM ml_forecast_daily
WHERE forecast_date >= CURRENT_DATE
ORDER BY metric_name, forecast_date;

-- ============================================
-- ADDITIONAL USEFUL QUERIES
-- ============================================

-- Daily Revenue with 7-day Moving Average
SELECT 
    full_date as "Date",
    total_revenue as "Daily Revenue",
    AVG(total_revenue) OVER (ORDER BY full_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as "7-Day Avg"
FROM mart_daily_kpis
ORDER BY full_date;

-- Week over Week Comparison
WITH weekly_data AS (
    SELECT 
        DATE_TRUNC('week', full_date) as week_start,
        SUM(total_revenue) as weekly_revenue,
        SUM(total_orders) as weekly_orders
    FROM mart_daily_kpis
    GROUP BY DATE_TRUNC('week', full_date)
)
SELECT 
    week_start as "Week",
    weekly_revenue as "Revenue",
    weekly_orders as "Orders",
    LAG(weekly_revenue) OVER (ORDER BY week_start) as "Previous Week Revenue",
    ROUND((weekly_revenue - LAG(weekly_revenue) OVER (ORDER BY week_start)) / 
          NULLIF(LAG(weekly_revenue) OVER (ORDER BY week_start), 0) * 100, 2) as "WoW Growth %"
FROM weekly_data
ORDER BY week_start;
