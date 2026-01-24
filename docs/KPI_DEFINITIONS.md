# KPI Definitions & Business Logic

This document defines all Key Performance Indicators (KPIs) used in the E-Commerce BI platform, including their business meaning, calculation logic, and usage context.

---

## Executive KPIs

### 1. Total Revenue

**Definition:** The total monetary value of all valid sales transactions.

**Business Meaning:** Primary measure of business performance and growth.

**Calculation:**
```sql
SUM(line_total) 
WHERE is_cancelled = FALSE AND is_return = FALSE
```

**Formula:** `Revenue = Σ (Quantity × Unit Price)` for valid transactions

**Granularity:** Can be calculated daily, weekly, monthly, or by any dimension.

**Usage:** 
- Executive dashboards
- Trend analysis
- Goal tracking

---

### 2. Total Orders

**Definition:** Count of unique invoices (transactions) excluding cancellations.

**Business Meaning:** Measures transaction volume and customer activity.

**Calculation:**
```sql
COUNT(DISTINCT invoice_no) 
WHERE is_cancelled = FALSE
```

**Note:** A single order can contain multiple line items.

**Usage:**
- Operational metrics
- Capacity planning
- Marketing effectiveness

---

### 3. Average Order Value (AOV)

**Definition:** Average revenue per order.

**Business Meaning:** Indicates customer purchasing behavior and basket size.

**Calculation:**
```sql
Total Revenue / Total Orders
```

**Formula:** `AOV = Revenue / Orders`

**Target:** Higher is generally better; monitor for significant drops.

**Usage:**
- Pricing strategy
- Promotion effectiveness
- Customer segmentation

---

### 4. Unique Customers

**Definition:** Count of distinct customers who made purchases.

**Business Meaning:** Measures customer base size and reach.

**Calculation:**
```sql
COUNT(DISTINCT customer_id) 
WHERE customer_id IS NOT NULL
```

**Note:** Records without customer_id are excluded (guest checkouts).

**Usage:**
- Market penetration
- Growth tracking
- Customer acquisition metrics

---

### 5. New Customers

**Definition:** Number of customers whose first-ever purchase occurred on the given day.

**Business Meaning:** Tracks acquisition effectiveness and brand reach.

**Calculation:**
```sql
COUNT(*)
FROM dim_customer
WHERE first_purchase_date = full_date
```

**Usage:**
- Acquisition tracking
- Campaign attribution
- Market expansion monitoring

---

### 6. Repeat Customers

**Definition:** Returning customers who purchased again on the given day.

**Business Meaning:** Measures retention and loyalty behavior.

**Calculation:**
```sql
unique_customers - new_customers
```

**Usage:**
- Retention monitoring
- Loyalty program effectiveness
- Churn risk signals

---

### 7. Cancellation Rate

**Definition:** Percentage of orders that were cancelled.

**Business Meaning:** Indicates potential issues with products, pricing, or customer experience.

**Calculation:**
```sql
Cancelled Orders / Total Orders × 100
```

**Where Cancelled:** `invoice_no LIKE 'C%'`

**Target:** Lower is better. Investigate spikes immediately.

**Benchmark:** Industry average ~2-5%

**Usage:**
- Quality control
- Customer satisfaction
- Process improvement

---

### 8. Return Rate

**Definition:** Percentage of orders with returns.

**Business Meaning:** Indicates product quality, description accuracy, or customer fit issues.

**Calculation:**
```sql
Return Orders / Total Orders × 100
```

**Where Return:** `quantity < 0`

**Target:** Lower is better.

**Benchmark:** E-commerce average ~15-30%

**Usage:**
- Product quality assessment
- Description accuracy
- Sizing/fit issues

---

## Customer Value KPIs (RFM)

### 9. Recency (R)

**Definition:** Number of days since customer's last purchase.

**Business Meaning:** Measures customer engagement freshness.

**Calculation:**
```sql
MAX(transaction_date) - last_transaction_date
```

**Scoring (1-5):**
- Score 5: Most recent (top 20%)
- Score 1: Least recent (bottom 20%)

**Usage:**
- Re-engagement campaigns
- Churn prediction
- Customer lifecycle

---

### 10. Frequency (F)

**Definition:** Total number of orders placed by a customer.

**Business Meaning:** Measures customer loyalty and repeat behavior.

**Calculation:**
```sql
COUNT(DISTINCT invoice_no) per customer
```

**Scoring (1-5):**
- Score 5: Most frequent (top 20%)
- Score 1: Least frequent (bottom 20%)

**Usage:**
- Loyalty programs
- VIP identification
- Retention strategies

---

### 11. Monetary (M)

**Definition:** Total amount spent by a customer.

**Business Meaning:** Measures customer lifetime value contribution.

**Calculation:**
```sql
SUM(line_total) per customer
WHERE is_cancelled = FALSE AND is_return = FALSE
```

**Scoring (1-5):**
- Score 5: Highest spenders (top 20%)
- Score 1: Lowest spenders (bottom 20%)

**Usage:**
- VIP treatment
- Marketing budget allocation
- Personalization

---

### 12. RFM Segment

**Definition:** Customer classification based on combined RFM scores.

**Business Meaning:** Identifies customer value tiers for targeted actions.

**Segments:**

| Segment | R | F | M | Action |
|---------|---|---|---|--------|
| Champions | 4-5 | 4-5 | 4-5 | Reward and retain |
| Loyal Customers | 4-5 | 3-5 | 3-5 | Upsell premium products |
| Recent Customers | 4-5 | 1-2 | - | Nurture relationship |
| Potential Loyalists | 3-5 | 3-5 | 3-5 | Offer membership |
| Promising | 3-5 | 1-2 | 2-5 | Increase engagement |
| Needs Attention | 2-3 | 1-2 | 1-2 | Reactivate |
| At Risk | 1-2 | 3-5 | - | Win back campaign |
| Can't Lose Them | 1-2 | 4-5 | 4-5 | Urgent reactivation |
| Hibernating | 1-2 | 1-2 | - | Consider lost |

---

## Product Performance KPIs

### 13. Product Revenue

**Definition:** Total revenue generated by a product.

**Calculation:**
```sql
SUM(line_total) per stock_code
WHERE is_cancelled = FALSE AND is_return = FALSE
```

**Usage:**
- Portfolio optimization
- Inventory decisions
- Pricing strategy

---

### 14. Product Quantity Sold

**Definition:** Total units sold of a product.

**Calculation:**
```sql
SUM(quantity) per stock_code
WHERE is_cancelled = FALSE AND is_return = FALSE
```

**Usage:**
- Demand forecasting
- Inventory management
- Reorder points

---

### 15. Revenue Rank

**Definition:** Product ranking by total revenue (1 = highest).

**Calculation:**
```sql
RANK() OVER (ORDER BY total_revenue DESC)
```

**Usage:**
- Pareto analysis (80/20 rule)
- Focus prioritization
- Assortment decisions

---

## Geographic KPIs

### 16. Country Revenue Share

**Definition:** Percentage of total revenue from a country.

**Calculation:**
```sql
Country Revenue / Total Revenue × 100
```

**Usage:**
- Market prioritization
- Expansion decisions
- Resource allocation

---

### 17. Country Orders Share

**Definition:** Percentage of total orders from a country.

**Calculation:**
```sql
Country Orders / Total Orders × 100
```

**Usage:**
- Operational planning
- Shipping optimization
- Market sizing

---

## ML/Forecasting KPIs

### 18. Predicted Revenue

**Definition:** ML model's forecast for future daily revenue.

**Model:** Facebook Prophet (time series forecasting)

**Features Used:**
- Historical daily revenue
- Yearly seasonality
- Weekly seasonality
- Trend component

**Output:**
- Point prediction
- Lower bound (80% confidence)
- Upper bound (80% confidence)

**Usage:**
- Planning
- Budgeting
- Anomaly baseline

---

### 19. Predicted Orders

**Definition:** ML model's forecast for future daily orders.

**Model:** Facebook Prophet

**Usage:**
- Capacity planning
- Staffing
- Inventory preparation

---

### 20. Anomaly Detection

**Definition:** Identification of unusual values in KPI time series.

**Model:** Isolation Forest

**Parameters:**
- Contamination: 10% (expected anomaly rate)
- Lookback: 30 days minimum

**Classification:**

| Deviation | Severity |
|-----------|----------|
| > 50% | Critical |
| 30-50% | High |
| 15-30% | Medium |
| < 15% | Low |

**Anomaly Types:**
- **Spike:** Actual > Expected
- **Drop:** Actual < Expected

**Usage:**
- Early warning system
- Root cause investigation
- Operational alerts

---

## Time-Based Calculations

### Growth Rates

**Month-over-Month (MoM):**
```sql
(Current Month - Previous Month) / Previous Month × 100
```

**Week-over-Week (WoW):**
```sql
(Current Week - Previous Week) / Previous Week × 100
```

**Year-over-Year (YoY):**
```sql
(Current Year - Previous Year) / Previous Year × 100
```

### Moving Averages

**7-Day Moving Average:**
```sql
AVG(metric) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)
```

**Usage:**
- Smooth out daily volatility
- Trend identification
- Baseline comparison

---

## Data Quality Rules

### Exclusions

The following are **excluded** from KPI calculations:

1. **Cancelled transactions:** `invoice_no LIKE 'C%'`
2. **Zero-quantity transactions:** `quantity = 0`
3. **Invalid prices:** `unit_price <= 0`
4. **Null invoice numbers:** `invoice_no IS NULL`

### Inclusions

The following are **included but flagged:**

1. **Returns:** `quantity < 0` (tracked separately)
2. **Guest checkouts:** `customer_id IS NULL` (excluded from customer KPIs only)

---

## Refresh Schedule

| KPI Category | Refresh Frequency | Source Table |
|--------------|-------------------|--------------|
| Daily KPIs | Every 6 hours | mart_daily_kpis |
| RFM Segments | Daily | mart_rfm |
| Country Performance | Every 6 hours | mart_country_performance |
| Product Performance | Every 6 hours | mart_product_performance |
| ML Forecasts | Daily | ml_forecast_daily |
| Anomaly Detection | Daily | ml_anomalies_daily |
