# E-Commerce BI Data Model Diagrams

## 🎯 Key Contributions & Story

This BI project transforms raw transactional data into **actionable business intelligence** through a modern data architecture:

### **Key Contributions:**

1. **Star Schema Design** - Optimized for analytical queries with fact/dimension separation
2. **RFM Customer Segmentation** - Advanced customer intelligence with 11 behavioral segments
3. **ML-Powered Forecasting** - Prophet-based predictions with confidence intervals
4. **Anomaly Detection** - Isolation Forest for automatic issue detection
5. **Multi-Layer Marts** - Pre-aggregated tables for sub-second dashboard performance
6. **Full Lineage Tracking** - Model versioning, backtest results, and data quality monitoring

---

## 📊 Star Schema - Core Data Model

```mermaid
erDiagram
    FACT_SALES ||--o{ DIM_DATE : "date_key"
    FACT_SALES ||--o{ DIM_CUSTOMER : "customer_key"
    FACT_SALES ||--o{ DIM_PRODUCT : "product_key"
    FACT_SALES ||--o{ DIM_COUNTRY : "country_key"

    FACT_SALES {
        int sales_key PK
        int date_key FK
        int customer_key FK
        int product_key FK
        int country_key FK
        varchar invoice_no
        int quantity
        decimal unit_price
        decimal line_total
        boolean is_cancelled
        boolean is_return
    }

    DIM_DATE {
        int date_key PK
        date full_date UK
        int year
        int quarter
        int month
        varchar month_name
        int week_of_year
        int day_of_month
        int day_of_week
        varchar day_name
        boolean is_weekend
        int fiscal_year
        int fiscal_quarter
    }

    DIM_CUSTOMER {
        int customer_key PK
        int customer_id UK
        date first_purchase_date
        date last_purchase_date
        int total_orders
        decimal total_revenue
        decimal avg_order_value
        varchar customer_segment
        int rfm_recency_score
        int rfm_frequency_score
        int rfm_monetary_score
        varchar rfm_segment
    }

    DIM_PRODUCT {
        int product_key PK
        varchar stock_code UK
        text description
        varchar product_category
        decimal avg_unit_price
        int total_quantity_sold
        decimal total_revenue
        date first_sold_date
        date last_sold_date
    }

    DIM_COUNTRY {
        int country_key PK
        varchar country_name UK
        varchar region
        int total_customers
        int total_orders
        decimal total_revenue
    }
```

---

## 🎯 BI Marts Layer - Analytics-Ready Tables

```mermaid
erDiagram
    MART_DAILY_KPIS ||--o{ DIM_DATE : "date_key"
    MART_RFM ||--o{ DIM_CUSTOMER : "customer_id"
    MART_COUNTRY_PERFORMANCE ||--o{ DIM_COUNTRY : "country_key"
    MART_PRODUCT_PERFORMANCE ||--o{ DIM_PRODUCT : "product_key"

    MART_DAILY_KPIS {
        int date_key PK
        date full_date UK
        decimal total_revenue
        int total_orders
        int total_items_sold
        int unique_customers
        decimal avg_order_value
        int cancelled_orders
        decimal cancelled_revenue
        int return_orders
        decimal return_revenue
        decimal cancellation_rate
        decimal return_rate
        int new_customers
        int repeat_customers
    }

    MART_RFM {
        int customer_id PK
        int recency_days
        int frequency
        decimal monetary
        int r_score "1-5"
        int f_score "1-5"
        int m_score "1-5"
        varchar rfm_score "e.g., 555"
        varchar rfm_segment "Champions, Loyal, etc."
        text segment_description
    }

    MART_COUNTRY_PERFORMANCE {
        int country_key PK
        varchar country_name
        decimal total_revenue
        int total_orders
        int total_customers
        decimal avg_order_value
        decimal revenue_share_pct
        decimal orders_share_pct
    }

    MART_PRODUCT_PERFORMANCE {
        int product_key PK
        varchar stock_code
        text description
        varchar product_category
        decimal total_revenue
        int total_quantity
        int total_orders
        decimal avg_unit_price
        int revenue_rank
        int quantity_rank
    }

    MART_MONTHLY_TRENDS {
        varchar year_month PK "YYYY-MM"
        int year
        int month
        decimal total_revenue
        int total_orders
        int total_customers
        decimal avg_order_value
        decimal revenue_mom_growth
        decimal orders_mom_growth
    }
```

---

## 🤖 ML Pipeline - Forecasting & Anomaly Detection

```mermaid
erDiagram
    ML_MODEL_RUNS ||--o{ ML_BACKTEST_RESULTS : "run_id"
    ML_MODEL_RUNS ||--o{ ML_FORECAST_DAILY : "model_run_id"
    ML_MODEL_RUNS ||--o{ ML_ANOMALIES_DAILY : "model_run_id"
    MART_DAILY_KPIS ||--o{ ML_FORECAST_DAILY : "feeds data to"
    MART_DAILY_KPIS ||--o{ ML_ANOMALIES_DAILY : "compares with"

    ML_MODEL_RUNS {
        int run_id PK
        timestamp run_timestamp
        varchar model_type "forecast_prophet/anomaly_isolation_forest"
        varchar target_metric "revenue/orders"
        date train_start_date
        date train_end_date
        int train_samples
        jsonb parameters
        decimal mape "Mean Absolute Percentage Error"
        decimal smape
        decimal rmse
        decimal mae
        decimal baseline_mape
        decimal improvement_vs_baseline_pct
        varchar model_version
        varchar status "completed/running/failed"
    }

    ML_BACKTEST_RESULTS {
        int backtest_id PK
        int run_id FK
        date prediction_date
        decimal actual_value
        decimal predicted_value
        decimal lower_bound
        decimal upper_bound
        decimal absolute_error
        decimal percentage_error
        boolean within_confidence_interval
    }

    ML_FORECAST_DAILY {
        date forecast_date PK
        varchar metric_name PK
        decimal predicted_value
        decimal lower_bound
        decimal upper_bound
        decimal confidence_level "0.95 default"
        int model_run_id FK
        varchar model_name
        varchar model_version
    }

    ML_ANOMALIES_DAILY {
        date anomaly_date PK
        varchar metric_name PK
        decimal actual_value
        decimal expected_value
        decimal lower_bound
        decimal upper_bound
        decimal deviation_pct
        decimal z_score
        varchar anomaly_type "spike/drop/outlier"
        varchar severity "low/medium/high/critical"
        boolean is_weekend
        int day_of_week
        text probable_cause
        text business_interpretation
        text recommended_action
        boolean is_alert_sent
        boolean acknowledged
        varchar acknowledged_by
    }
```

---

## 🔄 Complete Data Flow Architecture

```mermaid
graph TB
    subgraph "📥 INGESTION LAYER"
        A[Raw CSV Data<br/>541,909 transactions] -->|Workflow A| B[raw_transactions<br/>PostgreSQL table]
    end

    subgraph "🔧 ETL LAYER - Workflow B"
        B -->|Clean & Validate| C[staging_transactions<br/>Data Quality Checks]
        C -->|Build Dimensions| D1[dim_date]
        C -->|Build Dimensions| D2[dim_customer<br/>with RFM scores]
        C -->|Build Dimensions| D3[dim_product]
        C -->|Build Dimensions| D4[dim_country]
        C -->|Build Fact| F[fact_sales<br/>539,388 rows]
        D1 --> F
        D2 --> F
        D3 --> F
        D4 --> F
    end

    subgraph "📊 MART LAYER - Pre-Aggregated"
        F -->|Aggregate Daily| M1[mart_daily_kpis<br/>305 days]
        F -->|RFM Analysis| M2[mart_rfm<br/>4,338 customers]
        F -->|Country Rollup| M3[mart_country_performance<br/>38 countries]
        F -->|Product Rollup| M4[mart_product_performance<br/>3,937 products]
    end

    subgraph "🤖 ML LAYER - Workflow C"
        M1 -->|Prophet Training| ML1[ml_model_runs<br/>Track experiments]
        M1 -->|Isolation Forest| ML2[Anomaly Detection]
        ML1 -->|14-day forecast| ML3[ml_forecast_daily<br/>with confidence intervals]
        ML1 -->|365-day outlook| ML3
        ML2 -->|Detect outliers| ML4[ml_anomalies_daily<br/>with severity & recommendations]
        ML1 -->|Backtest| ML5[ml_backtest_results<br/>Validation metrics]
    end

    subgraph "📈 VISUALIZATION LAYER"
        M1 --> V1[Apache Superset<br/>Dashboards]
        M2 --> V1
        M3 --> V1
        M4 --> V1
        ML3 --> V1
        ML4 --> V1
    end

    style A fill:#e1f5ff
    style F fill:#fff4e6
    style M1 fill:#f3e5f5
    style M2 fill:#f3e5f5
    style M3 fill:#f3e5f5
    style M4 fill:#f3e5f5
    style ML3 fill:#e8f5e9
    style ML4 fill:#ffebee
    style V1 fill:#fce4ec
```

---

## 🎨 RFM Segmentation Logic

```mermaid
graph LR
    A[Customer Transaction History] --> B[Calculate RFM Metrics]
    B --> B1[Recency<br/>Days since last purchase]
    B --> B2[Frequency<br/>Total orders]
    B --> B3[Monetary<br/>Total revenue]
    
    B1 --> C[Quintile Scoring<br/>1-5 scale]
    B2 --> C
    B3 --> C
    
    C --> D{RFM Score<br/>Combination}
    
    D -->|555-544| E1[Champions<br/>Best customers]
    D -->|543-444| E2[Loyal Customers<br/>Regular buyers]
    D -->|433-344| E3[Potential Loyalists<br/>Growing engagement]
    D -->|551-512| E4[Recent Customers<br/>New high-spenders]
    D -->|155-144| E5[At Risk<br/>Previously active]
    D -->|255-244| E6[Need Attention<br/>Declining frequency]
    D -->|331-311| E7[About to Sleep<br/>Low recent activity]
    D -->|211-111| E8[Lost<br/>Inactive customers]
    
    E1 --> F[Targeted Marketing<br/>& Retention Strategies]
    E2 --> F
    E3 --> F
    E4 --> F
    E5 --> F
    E6 --> F
    E7 --> F
    E8 --> F
    
    style E1 fill:#4caf50
    style E2 fill:#8bc34a
    style E3 fill:#cddc39
    style E4 fill:#ffeb3b
    style E5 fill:#ff9800
    style E6 fill:#ff5722
    style E7 fill:#f44336
    style E8 fill:#9e9e9e
```

---

## 📊 Business Questions This Model Answers

| **Question** | **Data Source** | **Technique** |
|-------------|-----------------|---------------|
| **Are we growing?** | `mart_daily_kpis`, `mart_monthly_trends` | Time series analysis |
| **Where do we make money?** | `mart_country_performance`, `mart_product_performance` | Geographic & product segmentation |
| **Who are our best customers?** | `mart_rfm`, `dim_customer` | RFM behavioral segmentation |
| **What happens next week?** | `ml_forecast_daily` (14-day) | Prophet forecasting |
| **What about next year?** | `ml_forecast_daily` (365-day) | Long-term strategic outlook |
| **Did something break?** | `ml_anomalies_daily` | Isolation Forest detection |
| **Can we trust predictions?** | `ml_model_runs`, `ml_backtest_results` | MAPE vs baseline, backtesting |
| **Which customers are leaving?** | `mart_rfm` (At Risk, Lost segments) | RFM thresholds |
| **What drives cancellations?** | `mart_daily_kpis.cancellation_rate` | Trend analysis |

---

## 🏆 Why This Architecture Matters

### **Performance**
- ✅ **Sub-second queries** via pre-aggregated marts
- ✅ **Indexed foreign keys** on fact table (date, customer, product, country)
- ✅ **Composite indexes** for common query patterns

### **Flexibility**
- ✅ **Star schema** allows easy drill-down/roll-up
- ✅ **Modular marts** can be refreshed independently
- ✅ **JSONB parameters** in ML runs for schema evolution

### **Intelligence**
- ✅ **Automated forecasting** with Prophet (seasonal patterns, holidays)
- ✅ **Context-aware anomalies** (weekend/holiday flags, probable cause)
- ✅ **Model versioning** for reproducibility

### **Actionability**
- ✅ **Business interpretations** in anomaly table
- ✅ **Recommended actions** for each alert
- ✅ **Severity classification** for prioritization
- ✅ **RFM segment descriptions** for marketing campaigns

---

## 📏 Data Volumes (Current State)

```
Raw Data:          541,909 transactions
Fact Sales:        539,388 rows (after quality filters)
Dimensions:
  ├─ Countries:    38
  ├─ Products:     3,937
  ├─ Customers:    4,371
  └─ Date Range:   Dec 2010 - Dec 2011

Marts:
  ├─ Daily KPIs:   305 days
  ├─ RFM Segments: 4,338 customers
  ├─ Countries:    38 countries
  └─ Products:     3,937 products

ML Outputs:
  ├─ Forecasts:    14-day + 365-day horizons
  └─ Anomalies:    Auto-detected with severity levels
```

---

## 🎓 Educational Value

This project demonstrates:

1. **Dimensional Modeling** - Kimball methodology with slowly changing dimensions
2. **ETL Orchestration** - n8n workflows for reproducible pipelines
3. **Feature Engineering** - RFM scores, growth rates, aggregations
4. **Time Series ML** - Facebook Prophet with seasonality detection
5. **Unsupervised Learning** - Isolation Forest for outlier detection
6. **Model Ops** - Versioning, backtesting, baseline comparisons
7. **Data Quality** - Validation rules, staging layers, audit logs
8. **Visualization** - Apache Superset for self-service BI

---

*Generated from schema files in `/sql/init/`*
