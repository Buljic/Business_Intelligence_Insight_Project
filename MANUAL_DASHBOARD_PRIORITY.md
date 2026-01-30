# 🎯 Top Priority Visualizations - Manual Creation

## Prerequisites
**First, ensure these datasets exist in Superset:**
1. Go to: http://localhost:8088
2. Login: admin / admin123
3. Data → Datasets
4. Check if these exist:
   - `mart_daily_kpis`
   - `mart_country_performance`
   - `mart_monthly_trends`
   - `mart_rfm`
   - `ml_forecast_daily`
   - `v_active_alerts`

If missing, run "Setup Superset" button at http://localhost:8090

---

## 🔥 TIER 1: MUST-HAVE (Executive Dashboard)

### 1️⃣ Total Revenue - Big Number
**Dataset:** `mart_daily_kpis`
**Type:** Big Number
**Metric:** 
```sql
SUM(total_revenue)
```
**Format:** `$,.0f` (dollar with thousands separator)
**Title:** Total Revenue
**Subheader:** All-Time Performance

---

### 2️⃣ Total Orders - Big Number
**Dataset:** `mart_daily_kpis`
**Type:** Big Number
**Metric:** 
```sql
SUM(total_orders)
```
**Format:** `,d` (thousands separator)
**Title:** Total Orders
**Subheader:** Total Transactions

---

### 3️⃣ Average Order Value - Big Number
**Dataset:** `mart_daily_kpis`
**Type:** Big Number
**Metric:** 
```sql
AVG(avg_order_value)
```
**Format:** `$,.2f`
**Title:** Average Order Value
**Subheader:** Per Transaction

---

### 4️⃣ Revenue Trend - Line Chart
**Dataset:** `mart_daily_kpis`
**Type:** Time-series Line Chart
**Time Column:** `date`
**Time Grain:** Day
**Metric:** 
```sql
SUM(total_revenue)
```
**Title:** Revenue Over Time

---

### 5️⃣ Revenue by Country - Pie Chart
**Dataset:** `mart_country_performance`
**Type:** Pie Chart
**Metric:** 
```sql
SUM(total_revenue)
```
**Dimension:** `country_name`
**Format:** `$,.0f`
**Title:** Revenue by Country

---

## 📊 TIER 2: HIGH VALUE (RFM Analysis)

### 6️⃣ Total Customers - Big Number
**Dataset:** `mart_rfm`
**Type:** Big Number
**Metric:** 
```sql
COUNT(DISTINCT customer_id)
```
**Format:** `,d`
**Title:** Total Customers

---

### 7️⃣ Customer Segments - Pie Chart
**Dataset:** `mart_rfm`
**Type:** Pie Chart
**Metric:** 
```sql
COUNT(customer_id)
```
**Dimension:** `rfm_segment`
**Title:** Customer Segments Distribution

---

### 8️⃣ RFM Segment Analysis - Table
**Dataset:** `mart_rfm`
**Type:** Table
**Columns (Group By):** `rfm_segment`
**Metrics:**
```sql
COUNT(customer_id)
AVG(recency)
AVG(frequency)
AVG(monetary)
```
**Title:** RFM Segment Performance

---

## 🤖 TIER 3: ML INSIGHTS (If Time Allows)

### 9️⃣ Revenue Forecast - Line Chart
**Dataset:** `ml_forecast_daily`
**Type:** Time-series Line Chart
**Time Column:** `forecast_date`
**Time Grain:** Day
**Metrics:** 
```sql
AVG(predicted_value)
AVG(lower_bound)
AVG(upper_bound)
```
**Title:** 14-Day Revenue Forecast

---

### 🔟 Active Anomaly Alerts - Table
**Dataset:** `v_active_alerts`
**Type:** Table
**Columns (Group By):** 
- `anomaly_date`
- `metric_name`
- `severity`
- `anomaly_type`

**Metric:**
```sql
COUNT(*)
```
**Title:** Active Anomaly Alerts

---

## 🚀 Quick Start Guide

### Step 1: Create Big Number Charts (Charts 1-3, 6)
1. Charts → + Chart
2. Choose dataset
3. Chart Type: **Big Number**
4. Query Tab:
   - Click "Metrics" dropdown
   - Select "Custom SQL"
   - Paste metric SQL
   - Set format in "Customize" tab
5. Save with name

### Step 2: Create Line Charts (Charts 4, 9)
1. Charts → + Chart
2. Choose dataset
3. Chart Type: **Line Chart** (or Time-series Line)
4. Query Tab:
   - Time Column: Select column
   - Time Grain: Day
   - Metrics: Add custom SQL
5. Save with name

### Step 3: Create Pie Charts (Charts 5, 7)
1. Charts → + Chart
2. Choose dataset
3. Chart Type: **Pie Chart**
4. Query Tab:
   - Dimension: Select column
   - Metric: Add custom SQL
5. Save with name

### Step 4: Create Tables (Charts 8, 10)
1. Charts → + Chart
2. Choose dataset
3. Chart Type: **Table**
4. Query Tab:
   - Group By: Select dimension columns
   - Metrics: Add custom SQL metrics
5. Save with name

### Step 5: Create Dashboard
1. Dashboards → + Dashboard
2. Click "+" → Add existing charts
3. Drag charts to arrange
4. Save

---

## 📋 Recommended Order

**Start here (5 minutes):**
1. Total Revenue
2. Total Orders
3. Average Order Value
4. Revenue Trend

**Then add (5 minutes):**
5. Revenue by Country
6. Total Customers
7. Customer Segments

**Optional (10 minutes):**
8. RFM Segment Analysis
9. Revenue Forecast
10. Active Alerts

---

## 💡 Pro Tips

- **Use "Explore" mode** to test queries before saving
- **Copy successful charts** and modify instead of creating from scratch
- **Save after each chart** to avoid losing work
- **Use simple metrics first**, then enhance
- **Don't overcomplicate** - basic aggregations work best

---

## ✅ What You'll Have

**After Tier 1:** Executive dashboard with 5 KPIs
**After Tier 2:** + Customer segmentation insights
**After Tier 3:** + ML forecasting and anomaly detection

**Total Time:** 20-30 minutes for all tiers
