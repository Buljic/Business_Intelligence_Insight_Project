# Superset Dashboard Automation

## Overview

The BI Control Center now includes **one-click dashboard creation** for Apache Superset. Instead of manually creating each chart through the UI, you can generate complete dashboards with all charts automatically.

## What Gets Created

When you click **🚀 Auto-Create Dashboards**, the system will create:

### 1. Executive Overview Dashboard
**6 Charts:**
- **Total Revenue** (Big Number) - `$,.0f` format
- **Total Orders** (Big Number) - `,d` format  
- **Average Order Value** (Big Number) - `$,.2f` format
- **Revenue Trend** (Line Chart) - Daily revenue over time
- **Revenue by Country** (Pie Chart) - Geographic distribution
- **Monthly Performance** (Table) - Revenue, Orders, AOV by month

**Dataset:** `mart_daily_kpis`, `mart_country_performance`, `mart_monthly_trends`

---

### 2. Customer Segmentation (RFM) Dashboard
**3 Charts:**
- **Total Customers** (Big Number) - Distinct customer count
- **Segment Distribution** (Pie Chart) - Visual breakdown by RFM segment
- **Segment Performance** (Table) - Metrics by segment (Recency, Frequency, Monetary)

**Dataset:** `mart_rfm`

---

### 3. AI/ML Insights Dashboard
**3 Charts:**
- **Revenue Forecast** (Line Chart) - 14-day prediction with confidence bands
- **Active Alerts** (Table) - Current anomaly alerts
- **Model Performance** (Table) - MAPE and RMSE metrics

**Datasets:** `ml_forecast_daily`, `v_active_alerts`, `v_model_performance`

---

## How to Use

### Step 1: Setup Superset
First, ensure Superset is running and datasets are registered:

```bash
# From BI Control Center UI
1. Click "Setup Superset" button
2. Wait for confirmation (creates database connection + 14 datasets)
```

### Step 2: Auto-Create Dashboards
```bash
# From BI Control Center UI
1. Click "🚀 Auto-Create Dashboards" button
2. Wait 30-60 seconds (creates 12+ charts and 3 dashboards)
3. Check the output for dashboard URLs
```

### Step 3: Access Dashboards
```bash
# Open Superset
URL: http://localhost:8088
Username: admin
Password: admin123

# Navigate to Dashboards tab
# You'll see:
- Executive Overview
- Customer Segmentation (RFM)
- AI/ML Insights
```

---

## API Endpoint

### `POST /api/create-dashboards`

**Request:**
```bash
curl -X POST http://localhost:8080/api/create-dashboards
```

**Response:**
```json
{
  "status": "success",
  "charts_created": 12,
  "dashboards": [
    {
      "name": "Executive Overview",
      "id": 1,
      "charts": 6,
      "url": "http://superset:8088/superset/dashboard/1/"
    },
    {
      "name": "Customer Segmentation (RFM)",
      "id": 2,
      "charts": 3,
      "url": "http://superset:8088/superset/dashboard/2/"
    },
    {
      "name": "AI/ML Insights",
      "id": 3,
      "charts": 3,
      "url": "http://superset:8088/superset/dashboard/3/"
    }
  ],
  "errors": []
}
```

---

## Technical Details

### Architecture

**Module:** `ops_ui/superset_automation.py`

**Key Components:**
1. **SupersetAPI Class** - REST API client with authentication
2. **ChartDefinition** - Dataclass for chart configuration
3. **Chart Builders** - Functions that return chart definitions
4. **Dashboard Layout Generator** - Automatic grid positioning

### Authentication Flow
```python
1. POST /api/v1/security/login → Get JWT access_token
2. GET /api/v1/security/csrf_token/ → Get CSRF token
3. Include both in subsequent requests:
   - Header: Authorization: Bearer {access_token}
   - Header: X-CSRFToken: {csrf_token}
```

### Chart Creation Process
```python
1. Get dataset_id by table name
2. Build chart params (based on viz_type)
3. Build query_context (datasource + queries)
4. POST /api/v1/chart/ with payload
5. Return chart_id
```

### Dashboard Creation Process
```python
1. Create all charts, collect chart_ids
2. Build position_json (grid layout)
3. POST /api/v1/dashboard/ with layout
4. Return dashboard_id
```

---

## Customization

### Adding New Charts

Edit `superset_automation.py` and add to the appropriate function:

```python
def get_executive_charts() -> List[ChartDefinition]:
    return [
        # ... existing charts ...
        ChartDefinition(
            name="My Custom Chart",
            viz_type="echarts_timeseries_bar",
            dataset_name="mart_daily_kpis",
            metrics=["SUM(total_revenue)"],
            dimensions=["country_name"],
            title="Revenue by Country Over Time",
            time_column="date"
        )
    ]
```

### Supported Chart Types

| Viz Type | Description | Best For |
|----------|-------------|----------|
| `big_number_total` | Single KPI metric | Headlines, totals |
| `echarts_timeseries_line` | Line chart | Trends over time |
| `echarts_timeseries_bar` | Bar chart | Comparisons, time series |
| `echarts_area` | Stacked area | Cumulative trends |
| `pie` | Pie chart | Proportions, distributions |
| `table` | Data table | Detailed breakdowns |

### Custom Metrics

```python
metrics=["SUM(total_revenue)", "AVG(avg_order_value)", "COUNT(DISTINCT customer_id)"]
```

---

## Troubleshooting

### Issue: "Database 'ecommerce_dw' not found"
**Solution:** Run "Setup Superset" first to create the database connection

### Issue: "Dataset 'mart_daily_kpis' not found"
**Solution:** Ensure ETL has run and marts are populated
```bash
docker-compose exec ops_ui python -c "from main import run_query; print(run_query('SELECT COUNT(*) FROM mart_daily_kpis'))"
```

### Issue: "Authentication failed"
**Solution:** Check Superset credentials in environment variables
```bash
SUPERSET_USERNAME=admin
SUPERSET_PASSWORD=admin123
```

### Issue: Charts created but not visible
**Solution:** 
1. Clear browser cache
2. Log out and log back into Superset
3. Check Superset logs: `docker-compose logs superset`

---

## Benefits

### Before (Manual Creation)
⏱️ **Time:** 2-3 hours to create all charts manually
- Click through 15+ screens per chart
- Copy/paste SQL queries
- Configure formatting for each chart
- Position charts on dashboard grid

### After (Automated)
⏱️ **Time:** 30-60 seconds with one button click
✅ **Consistency:** All charts use same formatting standards
✅ **Reproducible:** Can recreate dashboards anytime
✅ **Version Control:** Chart definitions in code
✅ **Scalable:** Easy to add new dashboards

---

## Next Steps

1. **Customize Charts** - Modify chart definitions to match your needs
2. **Add Filters** - Enhance dashboards with native filters
3. **Set Refresh Rates** - Configure automatic data refresh
4. **Share Dashboards** - Grant access to team members
5. **Export/Import** - Use Superset's export feature for backups

---

## Related Documentation

- **Manual Instructions:** `docs/SUPERSET_DASHBOARD_GUIDE.md`
- **Data Model:** `docs/DATA_MODEL_DIAGRAMS.md`
- **API Reference:** https://superset.apache.org/docs/api/
