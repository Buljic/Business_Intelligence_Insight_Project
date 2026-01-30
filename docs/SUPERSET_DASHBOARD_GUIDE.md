# 📊 Apache Superset Dashboard Guide - Complete Setup Instructions

## 🎯 Overview

This guide provides **step-by-step instructions** for building 4 production-ready dashboards in Apache Superset for your e-commerce BI project.

---

## 🚀 Initial Setup

### Step 1: Access Superset
1. Open browser: `http://localhost:8088`
2. Login credentials: `admin` / `admin123`

### Step 2: Connect Database (One-Time Setup)

1. **Click** top menu: **Settings** (gear icon) → **Database Connections**
2. **Click** blue **+ Database** button (top right)
3. **Select** database type: **PostgreSQL**
4. Fill in connection details:
   ```
   Display Name: ecommerce_dw
   SQLAlchemy URI: postgresql://postgres:postgres123@postgres:5432/ecommerce_dw
   ```
5. **Click** **Test Connection** (should show green checkmark)
6. **Click** **Connect**

### Step 3: Create Datasets (One-Time Setup)

For each table below, follow these steps:

**Tables to add:**
- `mart_daily_kpis`
- `mart_rfm`
- `mart_country_performance`
- `mart_product_performance`
- `mart_monthly_trends`
- `ml_forecast_daily`
- `ml_anomalies_daily`
- `ml_model_runs`
- `fact_sales` (optional, for drill-downs)
- `dim_customer` (optional, for drill-downs)
- `dim_product` (optional, for drill-downs)
- `dim_country` (optional, for drill-downs)

**How to add each dataset:**
1. **Click** top menu: **Data** → **Datasets**
2. **Click** blue **+ Dataset** button (top right)
3. **Select:**
   - Database: `ecommerce_dw`
   - Schema: `public`
   - Table: (choose one from list above)
4. **Click** **Add**
5. **Repeat** for all tables

---

## 📈 Dashboard 1: Executive Overview - "How is the business performing?"

**Purpose:** High-level KPIs for C-suite and management  
**Audience:** Executives, managers  
**Key Questions:** Are we growing? What are key metrics?

### Dashboard Layout (4x3 grid)

```
┌─────────────────────────────────────────────────────┐
│  Total Revenue   │  Total Orders  │  Avg Order Value│
│   (Big Number)   │  (Big Number)  │   (Big Number)  │
├─────────────────────────────────────────────────────┤
│         Revenue & Orders Over Time                  │
│              (Dual-Axis Line Chart)                 │
├─────────────────────────────────────────────────────┤
│  Revenue by Country    │  New vs Repeat Customers   │
│     (Pie Chart)        │     (Stacked Area)         │
├─────────────────────────────────────────────────────┤
│     Monthly Performance Table                       │
│  (Shows: Month, Revenue, Orders, AOV, Growth%)      │
└─────────────────────────────────────────────────────┘
```

### Chart 1: Total Revenue (Big Number KPI)
1. **Click** **Charts** → **+ Chart**
2. **Choose:**
   - Dataset: `mart_daily_kpis`
   - Chart Type: **Big Number**
3. **Click** **Create New Chart**
4. **In Query panel:**
   - Metric: **Click** dropdown → **Custom SQL** → **Copy/paste:**
     ```sql
     SUM(total_revenue)
     ```
   - Name it: `Total Revenue`
5. **In Customize tab:**
   - Chart Title: `Total Revenue`
   - Subheader: `All-Time Performance`
   - Number Format: `$,.0f` (dollar with thousands separator)
6. **Click** **Save** → Name: `Executive - Total Revenue`

### Chart 2: Total Orders (Big Number KPI)
1. **Repeat** Chart 1 steps, but:
   - Metric SQL: `SUM(total_orders)`
   - Name: `Total Orders`
   - Number Format: `,d` (thousands separator, no decimals)
   - Save as: `Executive - Total Orders`

### Chart 3: Average Order Value (Big Number KPI)
1. **Repeat** Chart 1 steps, but:
   - Metric SQL: `AVG(avg_order_value)`
   - Name: `Avg Order Value`
   - Number Format: `$,.2f`
   - Save as: `Executive - Avg Order Value`

### Chart 4: Revenue & Orders Over Time (Line Chart)
1. **Charts** → **+ Chart** → Dataset: `mart_daily_kpis` → Type: **Line Chart**
2. **Query tab:**
   - **Time Column:** `full_date`
   - **Time Grain:** `Day` (raw data, no aggregation)
   - **Metrics:** 
     - **Click** + → Custom SQL: `SUM(total_revenue)` → Name: `Revenue`
     - **Click** + → Custom SQL: `SUM(total_orders)` → Name: `Orders`
   - **Row limit:** `10000`
3. **Customize tab:**
   - Chart Title: `Revenue & Orders Trend`
   - **Y-Axis (Left):** Revenue
   - **Y-Axis (Right):** Orders (check "Use right axis")
   - **Show Legend:** Yes
   - **Line Style:** Smooth
4. **Save** → `Executive - Revenue Orders Trend`

### Chart 5: Revenue by Country (Pie Chart)
1. **Charts** → **+ Chart** → Dataset: `mart_country_performance` → Type: **Pie Chart**
2. **Query tab:**
   - **Dimension:** `country_name`
   - **Metric:** Custom SQL: `SUM(total_revenue)` → Name: `Revenue`
   - **Row limit:** `10`
   - **Sort by:** `Revenue` (descending)
3. **Customize tab:**
   - Title: `Top 10 Countries by Revenue`
   - **Show Labels:** Yes
   - **Show Percentage:** Yes
   - **Legend Position:** Right
4. **Save** → `Executive - Country Revenue`

### Chart 6: New vs Repeat Customers (Stacked Area Chart)
1. **Charts** → **+ Chart** → Dataset: `mart_daily_kpis` → Type: **Area Chart**
2. **Query tab:**
   - **Time Column:** `full_date`
   - **Metrics:** 
     - Custom SQL: `SUM(new_customers)` → Name: `New`
     - Custom SQL: `SUM(repeat_customers)` → Name: `Repeat`
   - **Row limit:** `10000`
3. **Customize tab:**
   - Title: `Customer Acquisition vs Retention`
   - **Stack Area:** Yes (check this!)
   - **Show Legend:** Yes
4. **Save** → `Executive - Customer Type Trend`

### Chart 7: Monthly Performance Table
1. **Charts** → **+ Chart** → Dataset: `mart_daily_kpis` → Type: **Table**
2. **Query tab:**
   - **Metrics:**
     - Custom SQL: `TO_CHAR(full_date, 'YYYY-MM')` → Name: `Month` (put in **GROUP BY** section)
     - Custom SQL: `SUM(total_revenue)` → Name: `Revenue`
     - Custom SQL: `SUM(total_orders)` → Name: `Orders`
     - Custom SQL: `AVG(avg_order_value)` → Name: `AOV`
   - **Sort:** `Month` descending
   - **Row limit:** `24`
3. **Customize tab:**
   - Title: `Monthly Performance Summary`
   - **Number Formats:**
     - Revenue: `$,.0f`
     - Orders: `,d`
     - AOV: `$,.2f`
4. **Save** → `Executive - Monthly Table`

### Assemble Dashboard 1
1. **Dashboards** → **+ Dashboard**
2. **Name:** `Executive Overview`
3. **Drag charts** from right panel into layout
4. **Arrange** in grid (see layout diagram above)
5. **Add Filters:**
   - **Click** filter icon (funnel) → **Add Native Filter**
   - Type: **Time Range**
   - Target: All charts
   - Default: `Last 90 days`
6. **Save** dashboard

---

## 👥 Dashboard 2: Customer Segmentation - "Who are our best customers?"

**Purpose:** RFM-based customer intelligence  
**Audience:** Marketing, Sales  
**Key Questions:** Which customers to prioritize? Who's at risk?

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  Champions  │  Loyal     │  At Risk   │  Lost       │
│  (Big #)    │  (Big #)   │  (Big #)   │  (Big #)    │
├─────────────────────────────────────────────────────┤
│         RFM Segment Distribution                    │
│              (Pie Chart)                            │
├─────────────────────────────────────────────────────┤
│  Segment Performance Table                          │
│  (Customers, Avg Recency, Frequency, Monetary)      │
├─────────────────────────────────────────────────────┤
│  Top 20 Customers by Lifetime Value                 │
│              (Table)                                │
└─────────────────────────────────────────────────────┘
```

### Chart 1: Champions Count (Big Number)
1. **Dataset:** `mart_rfm` → **Chart Type:** Big Number
2. **Query:**
   - **Filters:** Add `rfm_segment` = `Champions`
   - **Metric:** `COUNT(*)` → Name: `Champions`
3. **Customize:**
   - Title: `Champions`
   - Subheader: `Best Customers`
   - Number Format: `,d`
4. **Save** → `RFM - Champions Count`

### Chart 2-4: Repeat for Loyal, At Risk, Lost
- Filter on respective segment
- Save with appropriate names

### Chart 5: RFM Segment Distribution (Pie Chart)
1. **Dataset:** `mart_rfm` → **Type:** Pie Chart
2. **Query:**
   - **Dimension:** `rfm_segment`
   - **Metric:** `COUNT(*)`
   - **Sort by:** Metric descending
3. **Customize:**
   - Title: `Customer Segments Distribution`
   - Show Labels: Yes
   - Show Percentage: Yes
4. **Save** → `RFM - Segment Pie`

### Chart 6: Segment Performance Table
1. **Dataset:** `mart_rfm` → **Type:** Table
2. **Query:**
   - **Columns (GROUP BY):** `rfm_segment`, `segment_description`
   - **Metrics:**
     - `COUNT(*)` → `Customers`
     - `AVG(recency_days)` → `Avg Recency`
     - `AVG(frequency)` → `Avg Frequency`
     - `AVG(monetary)` → `Avg Revenue`
   - **Sort:** Customers descending
3. **Customize:**
   - Title: `Segment Performance Details`
   - Number formats:
     - Customers: `,d`
     - Avg Recency: `,.0f` days
     - Avg Revenue: `$,.0f`
4. **Save** → `RFM - Segment Table`

### Chart 7: Top Customers Table
1. **Dataset:** `mart_rfm` → **Type:** Table
2. **Query:**
   - **Columns:** `customer_id`, `rfm_segment`, `recency_days`, `frequency`, `monetary`
   - **Sort:** `monetary` descending
   - **Row limit:** `20`
3. **Customize:**
   - Title: `Top 20 Customers by Lifetime Value`
   - Format monetary: `$,.0f`
4. **Save** → `RFM - Top Customers`

### Assemble Dashboard 2
1. **Create Dashboard:** `Customer Segmentation`
2. **Drag charts** into layout
3. **Add Filter:** RFM Segment (multi-select)
4. **Save**

---

## 📦 Dashboard 3: Product Performance - "What's selling?"

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│         Top 20 Products by Revenue                  │
│              (Horizontal Bar Chart)                 │
├─────────────────────────────────────────────────────┤
│  Product Revenue    │  Product Revenue Distribution │
│  Concentration      │       (Pie: Top10/11-50/Rest) │
│    (Big Number)     │                               │
├─────────────────────────────────────────────────────┤
│         Top 20 Products by Quantity                 │
│              (Horizontal Bar Chart)                 │
└─────────────────────────────────────────────────────┘
```

### Chart 1: Top Products by Revenue (Bar Chart)
1. **Dataset:** `mart_product_performance` → **Type:** Bar Chart
2. **Query:**
   - **Dimension:** Custom SQL: `LEFT(description, 50)` → Name: `Product`
   - **Metric:** `SUM(total_revenue)` → `Revenue`
   - **Sort:** Revenue descending
   - **Row limit:** `20`
3. **Customize:**
   - Title: `Top 20 Products by Revenue`
   - **Orientation:** Horizontal (bars go left-to-right)
   - **Show Values:** On bars
   - Format: `$,.0f`
4. **Save** → `Products - Top Revenue`

### Chart 2: Top Products by Quantity (Bar Chart)
1. **Similar to Chart 1**, but:
   - **Metric:** `SUM(total_quantity)`
   - Title: `Top 20 Products by Quantity Sold`
   - Format: `,d`
2. **Save** → `Products - Top Quantity`

### Chart 3: Revenue Concentration (Big Number)
1. **Dataset:** `mart_product_performance` → **Type:** Big Number with Trendline
2. **Query:**
   - **Metric:** Custom SQL:
     ```sql
     (SELECT SUM(total_revenue) FROM mart_product_performance WHERE revenue_rank <= 10) / 
     SUM(total_revenue) * 100
     ```
   - Name: `Top 10 Share %`
3. **Customize:**
   - Title: `Revenue Concentration`
   - Subheader: `Top 10 Products`
   - Format: `.1f%`
4. **Save** → `Products - Concentration`

### Assemble Dashboard 3
1. **Create Dashboard:** `Product Performance`
2. **Arrange charts**
3. **Add Filter:** Product Category (if available)
4. **Save**

---

## 🤖 Dashboard 4: AI/ML Insights - "What's next? What needs attention?"

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  Next 14D Revenue │  Next 14D Orders │ Critical     │
│  Forecast         │  Forecast        │ Alerts       │
│  (Big Number)     │  (Big Number)    │ (Big Number) │
├─────────────────────────────────────────────────────┤
│         14-Day Revenue Forecast vs Actual           │
│    (Line Chart with Confidence Bands)               │
├─────────────────────────────────────────────────────┤
│  Active Alerts Table                                │
│  (Date, Metric, Deviation, Severity, Action)        │
├─────────────────────────────────────────────────────┤
│  Model Performance  │  Anomaly Severity Distribution│
│      (Table)        │         (Pie Chart)           │
└─────────────────────────────────────────────────────┘
```

### Chart 1: 14-Day Revenue Forecast (Big Number)
1. **Dataset:** `ml_forecast_daily` → **Type:** Big Number
2. **Query:**
   - **Filters:** 
     - `metric_name` = `total_revenue`
     - `forecast_date` BETWEEN `NOW()` AND `NOW() + 13 days`
   - **Metric:** `SUM(predicted_value)`
3. **Customize:**
   - Title: `Next 14 Days Revenue`
   - Subheader: `Forecasted`
   - Format: `$,.0f`
4. **Save** → `ML - 14D Revenue Forecast`

### Chart 2: Critical Alerts Count (Big Number)
1. **Dataset:** `ml_anomalies_daily` → **Type:** Big Number
2. **Query:**
   - **Filters:** 
     - `severity` = `critical`
     - `acknowledged` = `false` (or IS NULL)
   - **Metric:** `COUNT(*)`
3. **Customize:**
   - Title: `Critical Alerts`
   - Subheader: `Require Attention`
   - **Color:** Red
4. **Save** → `ML - Critical Alerts`

### Chart 3: Revenue Forecast with Confidence Bands (Line Chart)
1. **Dataset:** `mart_daily_kpis` → **Type:** Mixed Time-Series Chart**
   - **Note:** You'll need to create a **CUSTOM SQL** dataset for this
2. **Create Custom Dataset:**
   - **Data** → **SQL Lab** → **SQL Editor**
   - **Paste query:**
     ```sql
     SELECT 
         COALESCE(mk.full_date, mf.forecast_date) as date,
         mk.total_revenue as actual,
         mf.predicted_value as forecast,
         mf.lower_bound,
         mf.upper_bound
     FROM mart_daily_kpis mk
     FULL OUTER JOIN ml_forecast_daily mf 
         ON mk.full_date = mf.forecast_date 
         AND mf.metric_name = 'total_revenue'
     ORDER BY date
     ```
   - **Save Dataset As:** `v_revenue_forecast_vs_actual`
3. **Create Chart:**
   - **Dataset:** `v_revenue_forecast_vs_actual` → **Type:** Line Chart
   - **Time:** `date`
   - **Metrics:** 
     - `AVG(actual)` → `Actual Revenue`
     - `AVG(forecast)` → `Forecast`
     - `AVG(lower_bound)` → `Lower Bound`
     - `AVG(upper_bound)` → `Upper Bound`
4. **Customize:**
   - Title: `Revenue: Actual vs 14-Day Forecast`
   - **Line Styles:**
     - Actual: Solid, bold
     - Forecast: Dashed
     - Bounds: Dotted, light
   - **Colors:**
     - Actual: Blue
     - Forecast: Orange
     - Bounds: Gray
5. **Save** → `ML - Revenue Forecast Chart`

### Chart 4: Active Alerts Table
1. **Dataset:** `ml_anomalies_daily` → **Type:** Table
2. **Query:**
   - **Columns:** `anomaly_date`, `metric_name`, `actual_value`, `expected_value`, `deviation_pct`, `severity`, `business_interpretation`, `recommended_action`
   - **Filters:** 
     - `acknowledged` = `false` OR NULL
     - `anomaly_date` >= `NOW() - 14 days`
   - **Sort:** Severity (custom sort: critical, high, medium, low)
   - **Row limit:** `50`
3. **Customize:**
   - Title: `Active Alerts - Action Required`
   - **Conditional Formatting:**
     - `severity` = `critical` → Red background
     - `severity` = `high` → Orange background
   - **Column Formats:**
     - `actual_value`: `,.0f`
     - `expected_value`: `,.0f`
     - `deviation_pct`: `.1f%`
4. **Save** → `ML - Active Alerts`

### Chart 5: Model Performance Table
1. **Dataset:** `ml_model_runs` → **Type:** Table
2. **Query:**
   - **Columns:** `target_metric`, `model_type`, `mape`, `baseline_mape`, `improvement_vs_baseline_pct`, `run_timestamp`
   - **Filters:** `status` = `completed`
   - **Sort:** `run_timestamp` descending
   - **Row limit:** `10`
3. **Customize:**
   - Title: `Model Performance - Last 10 Runs`
   - **Formats:**
     - MAPE: `.2f%`
     - Baseline: `.2f%`
     - Improvement: `.2f%`
4. **Save** → `ML - Model Performance`

### Chart 6: Anomaly Severity Distribution (Pie Chart)
1. **Dataset:** `ml_anomalies_daily` → **Type:** Pie Chart
2. **Query:**
   - **Dimension:** `severity`
   - **Metric:** `COUNT(*)`
3. **Customize:**
   - Title: `Anomaly Distribution by Severity`
   - **Color Scheme:**
     - critical: Red
     - high: Orange
     - medium: Yellow
     - low: Green
4. **Save** → `ML - Severity Pie`

### Assemble Dashboard 4
1. **Create Dashboard:** `AI/ML Insights`
2. **Arrange charts** (see layout above)
3. **Add Filters:**
   - **Time Range** (for historical anomalies)
   - **Metric Name** (revenue/orders filter)
4. **Save**

---

## 🎨 Best Practices Summary

### ✅ DO:
- **Use consistent color schemes** across all dashboards
- **Add meaningful titles** to every chart (not just "Chart 1")
- **Format numbers** appropriately (currency, percentages, thousands separator)
- **Limit charts** to 6-8 per dashboard (performance)
- **Add filters** for interactivity (date range, segments, countries)
- **Group related metrics** together in dashboard sections
- **Use big numbers** for KPIs at the top
- **Test on mobile** (responsive design)
- **Add data freshness indicators** (last updated timestamp)

### ❌ DON'T:
- **Overcrowd** dashboards with too many charts
- **Use default titles** like "Table 1" or "Chart"
- **Forget to format numbers** (raw decimals look unprofessional)
- **Mix different visual styles** (keep consistent)
- **Use 3D charts** or pie charts for more than 7 categories
- **Ignore loading times** (optimize queries with row limits)
- **Use too many colors** (3-5 max per chart)

---

## 🔧 Troubleshooting

### Charts not loading?
- Check **SQL Lab** → Run query manually to test
- Verify dataset has **data** (not empty table)
- Check **error logs** in browser console (F12)

### Slow dashboard performance?
- **Add row limits** to queries (10,000 max for line charts)
- **Enable caching:** Settings → Database → Edit → Enable cache
- **Pre-aggregate data** in marts (you already did this!)

### Numbers look wrong?
- Check **aggregation**: Are you using `SUM`, `AVG`, or `COUNT` correctly?
- **Group by** should only include dimensions, not metrics
- **Time grain** matters: Use `Day` for raw, `Month` for monthly

### Can't see future forecasts?
- **Remove time filter** on forecast charts (they show future dates)
- Or set filter to `All time` for ML charts

---

## 🎓 Learning Resources

- **Superset Docs:** https://superset.apache.org/docs/using-superset/creating-your-first-dashboard/
- **Chart Gallery:** Explore all 40+ chart types in **Charts** → **+ Chart**
- **SQL Lab:** Use for ad-hoc queries before creating charts

---

## 📞 Quick Reference: Chart Types by Use Case

| **Use Case** | **Best Chart Type** |
|-------------|-------------------|
| KPI (single number) | **Big Number** or **Big Number with Trendline** |
| Trend over time | **Line Chart** or **Area Chart** |
| Compare categories | **Bar Chart** (horizontal for long names) |
| Part-to-whole | **Pie Chart** (max 7 slices) or **Treemap** |
| Distribution | **Histogram** or **Box Plot** |
| Correlation | **Scatter Plot** or **Bubble Chart** |
| Detailed data | **Table** with conditional formatting |
| Geographic | **Map** (requires lat/long) |
| Forecast with uncertainty | **Line Chart** with multiple metrics (actual + bounds) |
| Ranking | **Bar Chart** sorted descending |

---

## 🏁 Next Steps After Building Dashboards

1. **Share dashboards** with team (Settings → Share → Copy link)
2. **Set up alerts** (if anomalies detected)
3. **Schedule email reports** (Dashboards → Edit → Email report)
4. **Export to PDF** (Dashboards → Export → PDF)
5. **Embed in website** (use iframe from share link)

Good luck! 🚀
