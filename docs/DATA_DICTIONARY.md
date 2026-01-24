# Data Dictionary

This document describes all tables, columns, and their meanings in the E-Commerce Data Warehouse.

## Source Data

### Original CSV Columns (data.csv)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| InvoiceNo | String | Invoice number (prefix 'C' = cancellation) | 536365, C536379 |
| StockCode | String | Product code | 85123A |
| Description | String | Product name/description | WHITE HANGING HEART T-LIGHT HOLDER |
| Quantity | Integer | Quantity purchased (negative = return) | 6, -2 |
| InvoiceDate | DateTime | Invoice date and time | 12/1/2010 8:26 |
| UnitPrice | Decimal | Price per unit in GBP | 2.55 |
| CustomerID | String | Customer identifier | 17850 |
| Country | String | Customer's country | United Kingdom |

---

## Raw Layer

### raw_transactions

Landing zone for CSV data ingestion.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | SERIAL | NO | Auto-generated primary key |
| invoice_no | VARCHAR(20) | YES | Original invoice number |
| stock_code | VARCHAR(20) | YES | Product code |
| description | TEXT | YES | Product description |
| quantity | INTEGER | YES | Quantity purchased |
| invoice_date | TIMESTAMP | YES | Transaction timestamp |
| unit_price | DECIMAL(10,2) | YES | Unit price |
| customer_id | VARCHAR(20) | YES | Customer ID (as string) |
| country | VARCHAR(100) | YES | Customer country |
| loaded_at | TIMESTAMP | NO | ETL load timestamp |

---

## Staging Layer

### stg_transactions_clean

Cleaned and validated transactions with business rules applied.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | SERIAL | NO | Auto-generated primary key |
| invoice_no | VARCHAR(20) | NO | Cleaned invoice number |
| stock_code | VARCHAR(20) | NO | Product code |
| description | TEXT | YES | Product description (default: 'Unknown') |
| quantity | INTEGER | NO | Quantity (non-zero) |
| invoice_date | TIMESTAMP | NO | Transaction timestamp |
| unit_price | DECIMAL(10,2) | NO | Unit price (> 0) |
| customer_id | INTEGER | YES | Customer ID (cast to integer) |
| country | VARCHAR(100) | NO | Country (default: 'Unknown') |
| line_total | DECIMAL(12,2) | YES | Calculated: quantity × unit_price |
| is_cancelled | BOOLEAN | NO | TRUE if invoice starts with 'C' |
| is_return | BOOLEAN | NO | TRUE if quantity < 0 |
| transformed_at | TIMESTAMP | NO | ETL transform timestamp |

**Business Rules Applied:**
- Removed records with null invoice_no, stock_code, or invoice_date
- Filtered records where unit_price ≤ 0
- Filtered records where quantity = 0
- Identified cancellations by 'C' prefix in invoice_no
- Identified returns by negative quantity

---

## Dimension Tables

### dim_date

Calendar dimension for time-based analysis.

| Column | Type | Description |
|--------|------|-------------|
| date_key | INTEGER | Primary key (YYYYMMDD format) |
| full_date | DATE | Full date value |
| year | INTEGER | Year (e.g., 2011) |
| quarter | INTEGER | Quarter (1-4) |
| month | INTEGER | Month (1-12) |
| month_name | VARCHAR(20) | Month name (e.g., 'January') |
| week_of_year | INTEGER | Week number (1-52) |
| day_of_month | INTEGER | Day of month (1-31) |
| day_of_week | INTEGER | Day of week (0=Sunday, 6=Saturday) |
| day_name | VARCHAR(20) | Day name (e.g., 'Monday') |
| is_weekend | BOOLEAN | TRUE if Saturday or Sunday |
| fiscal_year | INTEGER | Fiscal year |
| fiscal_quarter | INTEGER | Fiscal quarter |

### dim_customer

Customer dimension with RFM segmentation.

| Column | Type | Description |
|--------|------|-------------|
| customer_key | SERIAL | Surrogate key |
| customer_id | INTEGER | Natural key from source |
| first_purchase_date | DATE | First transaction date |
| last_purchase_date | DATE | Most recent transaction |
| total_orders | INTEGER | Lifetime order count |
| total_revenue | DECIMAL(12,2) | Lifetime revenue |
| avg_order_value | DECIMAL(10,2) | Average order value |
| customer_segment | VARCHAR(50) | Business segment |
| rfm_recency_score | INTEGER | RFM Recency (1-5) |
| rfm_frequency_score | INTEGER | RFM Frequency (1-5) |
| rfm_monetary_score | INTEGER | RFM Monetary (1-5) |
| rfm_segment | VARCHAR(50) | RFM segment name |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

### dim_product

Product dimension with aggregated metrics.

| Column | Type | Description |
|--------|------|-------------|
| product_key | SERIAL | Surrogate key |
| stock_code | VARCHAR(20) | Product SKU (natural key) |
| description | TEXT | Product description |
| product_category | VARCHAR(100) | Product category (derived) |
| avg_unit_price | DECIMAL(10,2) | Average selling price |
| total_quantity_sold | INTEGER | Total units sold |
| total_revenue | DECIMAL(12,2) | Total revenue generated |
| first_sold_date | DATE | First sale date |
| last_sold_date | DATE | Most recent sale |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

### dim_country

Geographic dimension.

| Column | Type | Description |
|--------|------|-------------|
| country_key | SERIAL | Surrogate key |
| country_name | VARCHAR(100) | Country name (natural key) |
| region | VARCHAR(100) | Geographic region |
| total_customers | INTEGER | Customer count |
| total_orders | INTEGER | Order count |
| total_revenue | DECIMAL(12,2) | Total revenue |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

---

## Fact Table

### fact_sales

Grain: One row per line item per transaction.

| Column | Type | Description |
|--------|------|-------------|
| sales_key | SERIAL | Surrogate key |
| date_key | INTEGER | FK to dim_date |
| customer_key | INTEGER | FK to dim_customer |
| product_key | INTEGER | FK to dim_product |
| country_key | INTEGER | FK to dim_country |
| invoice_no | VARCHAR(20) | Invoice number |
| quantity | INTEGER | Quantity purchased |
| unit_price | DECIMAL(10,2) | Unit price |
| line_total | DECIMAL(12,2) | Line total (qty × price) |
| is_cancelled | BOOLEAN | Cancellation flag |
| is_return | BOOLEAN | Return flag |
| created_at | TIMESTAMP | Record creation time |

---

## BI Marts

### mart_daily_kpis

Daily aggregated KPIs for executive dashboards and ML.

| Column | Type | Description |
|--------|------|-------------|
| date_key | INTEGER | PK, FK to dim_date |
| full_date | DATE | Date value |
| total_revenue | DECIMAL(14,2) | Daily revenue (excl. cancels/returns) |
| total_orders | INTEGER | Order count (excl. cancels) |
| total_items_sold | INTEGER | Items sold |
| unique_customers | INTEGER | Distinct customers |
| avg_order_value | DECIMAL(10,2) | Revenue / Orders |
| cancelled_orders | INTEGER | Cancelled order count |
| cancelled_revenue | DECIMAL(12,2) | Cancelled amount |
| return_orders | INTEGER | Return order count |
| return_revenue | DECIMAL(12,2) | Return amount |
| cancellation_rate | DECIMAL(5,4) | Cancels / Total orders |
| return_rate | DECIMAL(5,4) | Returns / Total orders |
| new_customers | INTEGER | First-time buyers |
| repeat_customers | INTEGER | Returning buyers |
| updated_at | TIMESTAMP | Last refresh time |

### mart_rfm

RFM customer segmentation.

| Column | Type | Description |
|--------|------|-------------|
| customer_id | INTEGER | Primary key |
| recency_days | INTEGER | Days since last purchase |
| frequency | INTEGER | Number of orders |
| monetary | DECIMAL(12,2) | Total spend |
| r_score | INTEGER | Recency score (1-5, 5=best) |
| f_score | INTEGER | Frequency score (1-5, 5=best) |
| m_score | INTEGER | Monetary score (1-5, 5=best) |
| rfm_score | VARCHAR(10) | Combined score (e.g., '555') |
| rfm_segment | VARCHAR(50) | Segment name |
| segment_description | TEXT | Segment description |
| updated_at | TIMESTAMP | Last refresh time |

**RFM Segments:**
- **Champions**: Best customers (R≥4, F≥4, M≥4)
- **Loyal Customers**: Consistent buyers
- **Recent Customers**: New buyers, need nurturing
- **Potential Loyalists**: Recent with potential
- **Promising**: Recent but low frequency
- **Needs Attention**: Above average but declining
- **At Risk**: Used to be active
- **Can't Lose Them**: High value at risk
- **Hibernating**: Low activity

### mart_country_performance

Country-level metrics.

| Column | Type | Description |
|--------|------|-------------|
| country_key | INTEGER | PK, FK to dim_country |
| country_name | VARCHAR(100) | Country name |
| total_revenue | DECIMAL(14,2) | Total revenue |
| total_orders | INTEGER | Order count |
| total_customers | INTEGER | Customer count |
| avg_order_value | DECIMAL(10,2) | AOV |
| revenue_share_pct | DECIMAL(5,2) | % of total revenue |
| orders_share_pct | DECIMAL(5,2) | % of total orders |
| updated_at | TIMESTAMP | Last refresh time |

### mart_product_performance

Product-level metrics with rankings.

| Column | Type | Description |
|--------|------|-------------|
| product_key | INTEGER | PK, FK to dim_product |
| stock_code | VARCHAR(20) | Product SKU |
| description | TEXT | Product description |
| product_category | VARCHAR(100) | Category |
| total_revenue | DECIMAL(14,2) | Total revenue |
| total_quantity | INTEGER | Units sold |
| total_orders | INTEGER | Order count |
| avg_unit_price | DECIMAL(10,2) | Average price |
| revenue_rank | INTEGER | Rank by revenue |
| quantity_rank | INTEGER | Rank by quantity |
| updated_at | TIMESTAMP | Last refresh time |

---

## ML Output Tables

### ml_forecast_daily

ML model predictions.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| forecast_date | DATE | Date being forecasted |
| metric_name | VARCHAR(50) | Metric (total_revenue, total_orders) |
| predicted_value | DECIMAL(14,2) | Predicted value |
| lower_bound | DECIMAL(14,2) | Lower confidence bound |
| upper_bound | DECIMAL(14,2) | Upper confidence bound |
| model_name | VARCHAR(100) | Model used (Prophet) |
| model_version | VARCHAR(20) | Model version |
| created_at | TIMESTAMP | Prediction timestamp |

### ml_anomalies_daily

Detected anomalies.

| Column | Type | Description |
|--------|------|-------------|
| id | SERIAL | Primary key |
| anomaly_date | DATE | Date of anomaly |
| metric_name | VARCHAR(50) | Affected metric |
| actual_value | DECIMAL(14,2) | Actual observed value |
| expected_value | DECIMAL(14,2) | Expected value |
| deviation_pct | DECIMAL(8,4) | Percentage deviation |
| anomaly_type | VARCHAR(20) | 'spike' or 'drop' |
| severity | VARCHAR(20) | 'critical', 'high', 'medium', 'low' |
| is_alert_sent | BOOLEAN | Alert notification status |
| created_at | TIMESTAMP | Detection timestamp |

**Severity Levels:**
- **Critical**: Deviation > 50%
- **High**: Deviation 30-50%
- **Medium**: Deviation 15-30%
- **Low**: Deviation < 15%
