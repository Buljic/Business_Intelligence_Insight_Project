-- ============================================
-- SUPERSET DASHBOARD QUERIES
-- Use these queries to create charts in Superset
-- ============================================
-- 
-- DASHBOARD DESIGN PRINCIPLES:
-- 1. Each dashboard answers a specific business question
-- 2. Flow: What happened? → Why? → What's next?
-- 3. Every chart has a clear purpose and title
-- 4. Consistent KPI definitions across all views
-- 5. Filters: Date range, Country, Segment, Top N products
--
-- RECOMMENDED FILTERS FOR ALL DASHBOARDS:
-- - Date Range: full_date BETWEEN :start_date AND :end_date
-- - Country: country_name IN (:selected_countries)
-- - Customer Segment: rfm_segment IN (:selected_segments)
--
-- ============================================

-- ============================================
-- DASHBOARD 1: EXECUTIVE OVERVIEW
-- Purpose: Answer "How is the business performing?"
-- Audience: C-suite, Management
-- Key Questions: Are we growing? What are our key metrics?
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
-- DASHBOARD 4: AI/ML INSIGHTS - "DEMAND OUTLOOK & ALERTS"
-- Purpose: Answer "What's next? What needs attention?"
-- Audience: Operations, Planning, Management
-- Key Questions: What's the 7-day demand forecast? Are there anomalies?
-- 
-- This is NOT a "random model output" page - it's a DECISION TOOL:
-- - "Next 7 Days Demand Outlook" with confidence bands
-- - "Alerts Requiring Attention" with business interpretation
-- - "Model Performance" to build trust in predictions
-- ============================================

-- SECTION: "7-DAY DEMAND OUTLOOK"
-- Chart Title: "Revenue Forecast - Next 7 Days"
-- Chart Description: "Prophet model forecast with 95% confidence interval. Use for inventory planning and staffing."
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

-- ============================================
-- ENHANCED AI/ML QUERIES FOR DECISION-MAKING
-- ============================================

-- SECTION: "ALERTS REQUIRING ATTENTION"
-- Chart Title: "Business Anomalies - Action Required"
-- Chart Description: "Unusual patterns detected by ML. Review and acknowledge to clear alerts."

-- Active Alerts Table (shows unacknowledged anomalies with business context)
SELECT 
    anomaly_date as "Date",
    metric_name as "Metric",
    ROUND(actual_value, 0) as "Actual",
    ROUND(expected_value, 0) as "Expected",
    ROUND(deviation_pct, 1) || '%' as "Deviation",
    UPPER(anomaly_type) as "Type",
    UPPER(severity) as "Severity",
    COALESCE(business_interpretation, 'Requires investigation') as "What Happened",
    COALESCE(recommended_action, 'Review and acknowledge') as "Recommended Action"
FROM ml_anomalies_daily
WHERE NOT COALESCE(acknowledged, FALSE)
  AND anomaly_date >= CURRENT_DATE - INTERVAL '14 days'
ORDER BY 
    CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
    anomaly_date DESC;

-- SECTION: "MODEL PERFORMANCE"
-- Chart Title: "Forecast Accuracy - Can You Trust These Predictions?"
-- Chart Description: "Model evaluation metrics vs naive baseline. Lower MAPE = better accuracy."

-- Model Performance Summary (for trust-building)
SELECT 
    target_metric as "Metric",
    ROUND(mape, 1) || '%' as "Model MAPE",
    ROUND(baseline_mape, 1) || '%' as "Baseline MAPE",
    ROUND(improvement_vs_baseline_pct, 1) || '%' as "Improvement",
    train_samples || ' days' as "Training Data",
    TO_CHAR(run_timestamp, 'YYYY-MM-DD HH24:MI') as "Last Trained"
FROM ml_model_runs
WHERE status = 'completed'
ORDER BY run_timestamp DESC
LIMIT 4;

-- SECTION: "7-DAY OUTLOOK SUMMARY"
-- Chart Title: "Next Week Demand Summary"
-- Use as KPI cards

-- Next 7 Days Total Revenue Forecast
SELECT 
    ROUND(SUM(predicted_value), 0) as "Forecasted Revenue",
    ROUND(SUM(lower_bound), 0) as "Conservative Estimate",
    ROUND(SUM(upper_bound), 0) as "Optimistic Estimate"
FROM ml_forecast_daily
WHERE metric_name = 'revenue'
  AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '6 days';

-- Next 7 Days Total Orders Forecast  
SELECT 
    ROUND(SUM(predicted_value), 0) as "Forecasted Orders",
    ROUND(SUM(lower_bound), 0) as "Conservative Estimate",
    ROUND(SUM(upper_bound), 0) as "Optimistic Estimate"
FROM ml_forecast_daily
WHERE metric_name = 'orders'
  AND forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '6 days';

-- ============================================
-- DATA FRESHNESS INDICATOR
-- Show on every dashboard footer
-- ============================================

-- Data Freshness Status (for dashboard "Last Updated" display)
SELECT 
    table_name as "Data Source",
    TO_CHAR(last_refresh_at, 'YYYY-MM-DD HH24:MI') as "Last Updated",
    row_count as "Records",
    CASE 
        WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '6 hours' THEN '🟢 Fresh'
        WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN '🟡 Stale'
        ELSE '🔴 Outdated'
    END as "Status"
FROM table_refresh_log
WHERE table_name IN ('mart_daily_kpis', 'mart_rfm', 'ml_forecast_daily')
ORDER BY last_refresh_at DESC;

-- ============================================
-- ACTIONABLE INSIGHTS QUERIES
-- ============================================

-- High-Value Customers At Risk (Action: Re-engagement campaign)
SELECT 
    customer_id as "Customer ID",
    ROUND(monetary, 2) as "Lifetime Value",
    recency_days as "Days Since Purchase",
    rfm_segment as "Current Segment",
    'Send re-engagement offer' as "Recommended Action"
FROM mart_rfm
WHERE rfm_segment IN ('At Risk', 'Cant Lose Them')
  AND monetary > (SELECT AVG(monetary) * 2 FROM mart_rfm)
ORDER BY monetary DESC
LIMIT 20;

-- Top Growing Countries (Action: Increase marketing spend)
SELECT 
    country_name as "Country",
    ROUND(total_revenue, 0) as "Revenue",
    total_orders as "Orders",
    total_customers as "Customers",
    ROUND(avg_order_value, 2) as "AOV",
    'Consider market expansion' as "Opportunity"
FROM mart_country_performance
WHERE total_customers > 10
ORDER BY total_revenue DESC
LIMIT 10;

-- Products Needing Attention (Low performance but high potential)
SELECT 
    stock_code as "SKU",
    LEFT(description, 40) as "Product",
    total_orders as "Orders",
    ROUND(total_revenue, 0) as "Revenue",
    ROUND(avg_unit_price, 2) as "Avg Price",
    'Review pricing/promotion' as "Action"
FROM mart_product_performance
WHERE revenue_rank BETWEEN 50 AND 200
  AND total_orders > 10
ORDER BY total_revenue DESC
LIMIT 15;
