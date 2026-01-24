# E-Commerce Business Intelligence Platform

A comprehensive BI solution for monitoring e-commerce performance using modern data stack technologies. This project demonstrates a complete data pipeline from raw CSV ingestion to ML-powered forecasting and interactive dashboards.

![Architecture](docs/diagrams/architecture_overview.png)

## 🎯 Project Goals

**Main Objective:** Improve e-commerce performance using BI by monitoring sales health, customer value, product performance, and predicting near-future demand while detecting abnormal drops/spikes early.

### Key Business Questions Answered

| Question | Solution |
|----------|----------|
| Are we growing? | Revenue/Orders/AOV trend dashboards |
| Where do we make money? | Country breakdown, product categories, top SKUs |
| Who are our best customers? | RFM segmentation analysis |
| What happens next week? | ML-powered 7-day forecasts |
| Did something break today? | Anomaly detection with alerts |

## 🏗️ Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CSV Data  │────▶│     n8n     │────▶│  PostgreSQL │────▶│  Superset   │
│  (Source)   │     │ (ETL/Orch)  │     │ (Warehouse) │     │ (Dashboards)│
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │
                           ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  FastAPI ML │────▶│   Reports   │
                    │  (AI/ML)    │     │  (Alerts)   │
                    └─────────────┘     └─────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Data Warehouse | PostgreSQL 15 | Storage, star schema, marts |
| ETL/Orchestration | n8n | Workflow automation, data pipelines |
| BI Dashboards | Apache Superset | Interactive visualizations |
| ML Service | FastAPI + Prophet | Forecasting & anomaly detection |
| Containerization | Docker Compose | One-command deployment |

## 🚀 Quick Start

### Prerequisites

- Docker Desktop installed and running
- Git (for cloning)
- 8GB+ RAM recommended

### One-Command Startup

```bash
# Clone the repository (or navigate to project folder)
cd "c:\Users\enit-024\Desktop\Fakultet\Master Studij\7 semestar\Poslovna Inteligencija\99 Projekat"

# Start all services
docker-compose up -d

# Wait for services to initialize (2-3 minutes)
# Check status
docker-compose ps
```

### Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **n8n** (ETL) | http://localhost:5678 | admin / admin123 |
| **Superset** (BI) | http://localhost:8088 | admin / admin123 |
| **ML API** | http://localhost:8000 | - |
| **PostgreSQL** | localhost:5432 | postgres / postgres123 |

## 📊 Data Pipeline

### Workflow A: CSV Ingestion
Loads raw e-commerce data from `data.csv` into `raw_transactions` table.

```
CSV File → Read → Parse → Batch (1000 rows) → PostgreSQL
```

### Workflow B: ETL Transforms
Transforms raw data into star schema with quality rules applied.

```
raw_transactions → stg_transactions_clean → Dimensions → fact_sales → Marts
```

**Data Quality Rules Applied:**
- Remove null invoice numbers
- Filter invalid prices (≤ 0)
- Identify cancellations (Invoice starts with 'C')
- Identify returns (negative quantity)
- Type casting and standardization

### Workflow C: ML Pipeline
Generates forecasts and detects anomalies.

```
mart_daily_kpis → ML Service → Forecasts + Anomalies → Database + Reports
```

## 📈 Running the Workflows

### Step 1: Ingest Data (Workflow A)

1. Open n8n: http://localhost:5678
2. Import workflow from `n8n/workflows/workflow_a_csv_ingestion.json`
3. Configure PostgreSQL credentials
4. Execute the workflow

### Step 2: Run ETL Transforms (Workflow B)

1. Import `n8n/workflows/workflow_b_etl_transforms.json`
2. Execute to populate star schema and marts

### Step 3: Generate ML Predictions (Workflow C)

1. Import `n8n/workflows/workflow_c_ml_pipeline.json`
2. Execute to generate forecasts and detect anomalies

**Alternative: Direct SQL**

```sql
-- Run full ETL pipeline
SELECT * FROM run_full_etl();
```

## 🎨 Dashboards

### 1. Executive Overview
- Revenue & Orders trend lines
- Country performance breakdown
- KPI cards (Total Revenue, Orders, Customers, AOV)
- Cancellation & Return rates

### 2. Customer Value (RFM)
- RFM segment distribution
- Customer segment details
- Top customers by value
- Segment health metrics

### 3. Product Performance
- Top 20 products by revenue
- Top 20 products by quantity
- Product tier analysis
- Sales trends by product

### 4. AI/ML Dashboard
- Actual vs Forecast comparison
- 7-day revenue forecast
- 7-day orders forecast
- Anomaly detection table
- Alert severity breakdown

## 🤖 ML Service API

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/forecast` | Generate forecast for metric |
| POST | `/anomalies` | Detect anomalies in metric |
| POST | `/train` | Train all models & generate outputs |
| GET | `/forecasts/latest` | Get latest forecasts |
| GET | `/anomalies/latest` | Get latest anomalies |

### Example: Generate Forecast

```bash
curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"metric": "total_revenue", "forecast_days": 7}'
```

### Example: Run Full Training

```bash
curl -X POST http://localhost:8000/train
```

## 📁 Project Structure

```
├── docker-compose.yml          # Container orchestration
├── data.csv                    # Source data (Kaggle E-Commerce)
├── README.md                   # This file
│
├── sql/
│   └── init/
│       ├── 01_raw_tables.sql   # Raw & staging tables
│       ├── 02_star_schema.sql  # Dimensional model
│       ├── 03_marts.sql        # BI marts & ML output tables
│       └── 04_etl_procedures.sql # ETL functions
│
├── ml_service/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                 # FastAPI ML service
│
├── n8n/
│   └── workflows/
│       ├── workflow_a_csv_ingestion.json
│       ├── workflow_b_etl_transforms.json
│       └── workflow_c_ml_pipeline.json
│
├── superset/
│   ├── superset_config.py
│   └── dashboards/
│       └── dashboard_queries.sql
│
├── scripts/
│   └── setup_superset.py       # Automated Superset setup
│
├── reports/                    # ML-generated reports
│
└── docs/
    ├── DATA_DICTIONARY.md
    ├── KPI_DEFINITIONS.md
    ├── BUSINESS_STORY.md
    └── diagrams/
        ├── star_schema.drawio
        └── etl_flow.drawio
```

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_USER | postgres | Database user |
| POSTGRES_PASSWORD | postgres123 | Database password |
| POSTGRES_DB | ecommerce_dw | Database name |
| N8N_BASIC_AUTH_USER | admin | n8n username |
| N8N_BASIC_AUTH_PASSWORD | admin123 | n8n password |

### Ports

| Service | Port |
|---------|------|
| PostgreSQL | 5432 |
| n8n | 5678 |
| Superset | 8088 |
| ML Service | 8000 |

## 🛑 Stopping the Stack

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## 📚 Documentation

- [Data Dictionary](docs/DATA_DICTIONARY.md) - Table and column definitions
- [KPI Definitions](docs/KPI_DEFINITIONS.md) - Business logic for metrics
- [Business Story](docs/BUSINESS_STORY.md) - Project narrative and insights

## 🐛 Troubleshooting

### Superset won't start
```bash
# Check logs
docker-compose logs superset

# Restart
docker-compose restart superset
```

### ML Service errors
```bash
# Check if mart tables are populated
docker exec -it ecommerce_postgres psql -U postgres -d ecommerce_dw -c "SELECT COUNT(*) FROM mart_daily_kpis;"
```

### n8n workflow fails
1. Verify PostgreSQL credentials in n8n
2. Check that raw data has been ingested
3. Review workflow execution logs

## 📄 License

This project is for educational purposes as part of the Business Intelligence course.

## 👥 Contributors

- Student Project - Master's Program, 7th Semester
- Course: Business Intelligence (Poslovna Inteligencija)

---

**Note:** The dataset used is the [UCI Online Retail Dataset](https://www.kaggle.com/datasets/carrie1/ecommerce-data) from Kaggle.
