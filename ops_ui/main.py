import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from superset_automation import automate_superset_dashboards

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ops_ui")

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.getenv("DATABASE_URL")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://ml_service:8000")
SUPERSET_URL = os.getenv("SUPERSET_URL", "http://superset:8088")
SUPERSET_USERNAME = os.getenv("SUPERSET_USERNAME", "admin")
SUPERSET_PASSWORD = os.getenv("SUPERSET_PASSWORD", "admin123")
CSV_PRIMARY_PATH = os.getenv("CSV_PATH", "/data/data.csv")
CSV_FALLBACK_PATH = os.getenv("CSV_FALLBACK_PATH", "/data/source.csv")

if not DATABASE_URL:
    logger.warning("DATABASE_URL is not set")

app = FastAPI(title="BI Control Center")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class BacktestRequest(BaseModel):
    metric: str
    model: str = "auto"
    test_days: int = 14


class ImportRequest(BaseModel):
    run_etl: bool = True
    run_ml: bool = False
    csv_path: Optional[str] = None


QUERY_LIBRARY: Dict[str, Dict[str, str]] = {
    "executive_summary": {
        "title": "Executive Summary KPIs",
        "sql": """
            SELECT
                MIN(full_date) as start_date,
                MAX(full_date) as end_date,
                ROUND(SUM(total_revenue), 0) as total_revenue,
                SUM(total_orders) as total_orders,
                SUM(unique_customers) as unique_customers,
                ROUND(AVG(NULLIF(avg_order_value, 0)), 2) as avg_order_value,
                ROUND(AVG(cancellation_rate) * 100, 2) as cancellation_rate_pct,
                ROUND(AVG(return_rate) * 100, 2) as return_rate_pct
            FROM mart_daily_kpis;
        """
    },
    "country_top10": {
        "title": "Top Countries by Revenue",
        "sql": """
            SELECT
                country_name,
                ROUND(total_revenue, 0) as total_revenue,
                total_orders,
                total_customers,
                ROUND(avg_order_value, 2) as avg_order_value
            FROM mart_country_performance
            ORDER BY total_revenue DESC
            LIMIT 10;
        """
    },
    "rfm_segments": {
        "title": "RFM Segment Distribution",
        "sql": """
            SELECT
                rfm_segment,
                COUNT(*) as customers,
                ROUND(SUM(monetary), 2) as total_revenue
            FROM mart_rfm
            GROUP BY rfm_segment
            ORDER BY customers DESC;
        """
    },
    "latest_anomalies": {
        "title": "Latest Anomalies",
        "sql": """
            SELECT
                anomaly_date,
                metric_name,
                ROUND(actual_value, 2) as actual_value,
                ROUND(expected_value, 2) as expected_value,
                ROUND(deviation_pct, 2) as deviation_pct,
                anomaly_type,
                severity,
                business_interpretation
            FROM ml_anomalies_daily
            ORDER BY anomaly_date DESC,
                CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3 ELSE 4 END
            LIMIT 15;
        """
    },
    "forecast_next_7d": {
        "title": "Forecast Next 14 Days",
        "sql": """
            SELECT
                forecast_date,
                metric_name,
                ROUND(predicted_value, 2) as predicted_value,
                ROUND(lower_bound, 2) as lower_bound,
                ROUND(upper_bound, 2) as upper_bound
            FROM ml_forecast_daily
            WHERE forecast_date >= CURRENT_DATE
            ORDER BY metric_name, forecast_date
            LIMIT 28;
        """
    },
    "data_freshness": {
        "title": "Data Freshness",
        "sql": """
            SELECT
                table_name,
                TO_CHAR(last_refresh_at, 'YYYY-MM-DD HH24:MI') as last_updated,
                row_count,
                CASE
                    WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '6 hours' THEN 'fresh'
                    WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 'stale'
                    ELSE 'outdated'
                END as status
            FROM table_refresh_log
            WHERE table_name IN ('mart_daily_kpis', 'mart_rfm', 'ml_forecast_daily')
            ORDER BY last_refresh_at DESC;
        """
    },
    "yearly_outlook": {
        "title": "Yearly Strategic Outlook",
        "sql": """
            WITH forecast_year AS (
                SELECT
                    SUM(CASE WHEN metric_name = 'total_revenue' THEN predicted_value ELSE 0 END) as forecast_revenue,
                    SUM(CASE WHEN metric_name = 'total_orders' THEN predicted_value ELSE 0 END) as forecast_orders
                FROM ml_forecast_daily
                WHERE forecast_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '364 days'
            ),
            actual_year AS (
                SELECT
                    SUM(total_revenue) as actual_revenue,
                    SUM(total_orders) as actual_orders
                FROM mart_daily_kpis
                WHERE full_date >= (SELECT MAX(full_date) - INTERVAL '365 days' FROM mart_daily_kpis)
            )
            SELECT
                ROUND(forecast_revenue, 0) as forecast_revenue_365d,
                ROUND(actual_revenue, 0) as last_365d_revenue,
                ROUND(forecast_revenue - actual_revenue, 0) as delta_revenue,
                ROUND((forecast_revenue - actual_revenue) / NULLIF(actual_revenue, 0) * 100, 2) as delta_revenue_pct,
                ROUND(forecast_orders, 0) as forecast_orders_365d,
                ROUND(actual_orders, 0) as last_365d_orders,
                ROUND(forecast_orders - actual_orders, 0) as delta_orders,
                ROUND((forecast_orders - actual_orders) / NULLIF(actual_orders, 0) * 100, 2) as delta_orders_pct
            FROM forecast_year, actual_year;
        """
    }
}


def connect_db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(DATABASE_URL)


def run_query(sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
    conn = connect_db()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.commit()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def run_statement(sql: str, params: Optional[List[Any]] = None) -> None:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def create_run_log(run_type: str) -> int:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO etl_run_log (run_type, status)
                VALUES (%s, 'running')
                RETURNING run_id
                """,
                (run_type,)
            )
            run_id = cur.fetchone()[0]
        conn.commit()
        return run_id
    finally:
        conn.close()


def update_run_log(run_id: int, status: str, error_message: Optional[str]) -> None:
    run_statement(
        """
        UPDATE etl_run_log
        SET status = %s,
            completed_at = CURRENT_TIMESTAMP,
            error_message = %s
        WHERE run_id = %s
        """,
        [status, error_message, run_id]
    )


def resolve_csv_path(custom_path: Optional[str]) -> Path:
    if custom_path:
        path = Path(custom_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"CSV not found at {custom_path}")
    primary = Path(CSV_PRIMARY_PATH)
    if primary.exists():
        return primary
    fallback = Path(CSV_FALLBACK_PATH)
    if fallback.exists():
        return fallback
    raise FileNotFoundError("CSV not found. Expected /data/data.csv or /data/source.csv.")


def import_csv_data(csv_path: Path) -> int:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE raw_transactions;")
            cur.execute("SET datestyle TO 'ISO, MDY';")
            with open(csv_path, "rb") as handle:
                cur.copy_expert(
                    """
                    COPY raw_transactions (
                        invoice_no, stock_code, description, quantity,
                        invoice_date, unit_price, customer_id, country
                    ) FROM STDIN WITH (FORMAT csv, HEADER true, ENCODING 'LATIN1');
                    """,
                    handle
                )
        conn.commit()
        rows = run_query("SELECT COUNT(*) as row_count FROM raw_transactions;")
        return int(rows[0]["row_count"])
    finally:
        conn.close()


def superset_login(session: requests.Session) -> None:
    login_url = f"{SUPERSET_URL.rstrip('/')}/api/v1/security/login"
    payload = {
        "username": SUPERSET_USERNAME,
        "password": SUPERSET_PASSWORD,
        "provider": "db",
        "refresh": True
    }
    response = session.post(login_url, json=payload, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"Superset login failed: {response.text}")
    token = response.json()["access_token"]
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Referer": SUPERSET_URL
    })


def superset_get_csrf(session: requests.Session) -> None:
    csrf_url = f"{SUPERSET_URL.rstrip('/')}/api/v1/security/csrf_token/"
    response = session.get(csrf_url, timeout=15)
    if response.status_code == 200:
        session.headers["X-CSRFToken"] = response.json()["result"]


def superset_create_db(session: requests.Session) -> int:
    db_url = f"{SUPERSET_URL.rstrip('/')}/api/v1/database/"
    
    # First, check if database already exists
    logger.info("Checking for existing Superset database...")
    try:
        response = session.get(db_url, timeout=15)
        if response.status_code == 200:
            databases = response.json().get("result", [])
            for db in databases:
                db_name = db.get("database_name", "")
                sqlalchemy_uri = db.get("sqlalchemy_uri", "")
                if "ecommerce" in db_name.lower() or "ecommerce_dw" in sqlalchemy_uri:
                    logger.info(f"Found existing database: {db_name} (ID: {db['id']})")
                    return int(db["id"])
    except Exception as e:
        logger.warning(f"Could not check existing databases: {e}")
    
    # Create new database
    logger.info("Creating new Superset database connection...")
    payload = {
        "database_name": "ecommerce_dw",
        "sqlalchemy_uri": "postgresql://postgres:postgres123@postgres:5432/ecommerce_dw",
        "expose_in_sqllab": True,
        "allow_ctas": True,
        "allow_cvas": True,
        "allow_dml": False,
        "allow_run_async": True,
        "cache_timeout": 0,
        "extra": json.dumps({
            "metadata_params": {},
            "engine_params": {},
            "metadata_cache_timeout": {},
            "schemas_allowed_for_file_upload": ["public"]
        })
    }
    
    try:
        response = session.post(db_url, json=payload, timeout=30)
        if response.status_code in (200, 201):
            db_id = int(response.json()["id"])
            logger.info(f"Successfully created database with ID: {db_id}")
            return db_id
        else:
            logger.error(f"Database creation failed: {response.status_code} - {response.text}")
            raise RuntimeError(f"Failed to create Superset database: {response.text}")
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise RuntimeError(f"Failed to connect to Superset: {str(e)}")


def superset_create_dataset(session: requests.Session, db_id: int, table_name: str) -> None:
    dataset_url = f"{SUPERSET_URL.rstrip('/')}/api/v1/dataset/"
    
    # Check if dataset already exists
    try:
        response = session.get(dataset_url, timeout=15)
        if response.status_code == 200:
            datasets = response.json().get("result", [])
            for ds in datasets:
                if ds.get("table_name") == table_name and ds.get("database", {}).get("id") == db_id:
                    logger.info(f"Dataset '{table_name}' already exists")
                    return
    except Exception as e:
        logger.warning(f"Could not check existing datasets: {e}")
    
    # Create dataset
    payload = {
        "database": db_id,
        "schema": "public",
        "table_name": table_name
    }
    
    try:
        response = session.post(dataset_url, json=payload, timeout=30)
        if response.status_code in (200, 201):
            logger.info(f"Created dataset: {table_name}")
        else:
            logger.warning(f"Dataset creation for '{table_name}' returned {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to create dataset '{table_name}': {e}")


@app.get("/", response_class=FileResponse)
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    db_ok = True
    ml_ok = False
    ml_status = None

    try:
        run_query("SELECT 1 as ok;")
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)
        db_ok = False

    try:
        response = requests.get(f"{ML_SERVICE_URL.rstrip('/')}/health", timeout=5)
        ml_ok = response.status_code == 200
        ml_status = response.json() if response.status_code == 200 else None
    except requests.RequestException as exc:
        logger.error("ML health check failed: %s", exc)

    return {
        "database_connected": db_ok,
        "ml_connected": ml_ok,
        "ml_status": ml_status
    }


@app.post("/api/run-etl")
async def run_etl() -> JSONResponse:
    try:
        rows = run_query("SELECT * FROM run_full_etl();")
        return JSONResponse({"status": "success", "steps": rows})
    except Exception as exc:
        logger.error("ETL failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run-dq")
async def run_dq() -> JSONResponse:
    run_id = create_run_log("manual_dq")
    try:
        results = run_query("SELECT * FROM run_data_quality_checks(%s, TRUE);", [run_id])
        has_critical = any((not row["passed"] and row["severity"] == "critical") for row in results)
        status = "failed" if has_critical else "success"
        update_run_log(run_id, status, None)
        return JSONResponse({"status": status, "run_id": run_id, "checks": results})
    except Exception as exc:
        update_run_log(run_id, "failed", str(exc))
        logger.error("DQ failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/import-csv")
async def import_csv(request: ImportRequest) -> JSONResponse:
    try:
        csv_path = resolve_csv_path(request.csv_path)
        row_count = import_csv_data(csv_path)
        response: Dict[str, Any] = {
            "status": "success",
            "csv_path": str(csv_path),
            "raw_rows": row_count
        }
        if request.run_etl:
            response["etl_steps"] = run_query("SELECT * FROM run_full_etl();")
        if request.run_ml:
            ml_response = requests.post(f"{ML_SERVICE_URL.rstrip('/')}/train", timeout=120)
            if ml_response.status_code >= 400:
                raise HTTPException(status_code=500, detail=ml_response.text)
            response["ml_result"] = ml_response.json()
        return JSONResponse(response)
    except Exception as exc:
        logger.error("CSV import failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/train-ml")
async def train_ml() -> JSONResponse:
    try:
        response = requests.post(f"{ML_SERVICE_URL.rstrip('/')}/train", timeout=120)
        if response.status_code >= 400:
            raise HTTPException(status_code=500, detail=response.text)
        return JSONResponse({"status": "success", "result": response.json()})
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/run-weekly-now")
async def run_weekly_now() -> JSONResponse:
    try:
        response = requests.post(f"{ML_SERVICE_URL.rstrip('/')}/train", timeout=180)
        if response.status_code >= 400:
            raise HTTPException(status_code=500, detail=response.text)
        anomalies = run_query(
            """
            SELECT
                anomaly_date,
                metric_name,
                severity,
                anomaly_type,
                ROUND(deviation_pct, 2) as deviation_pct
            FROM ml_anomalies_daily
            WHERE anomaly_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY anomaly_date DESC
            LIMIT 10;
            """
        )
        return JSONResponse({
            "status": "success",
            "result": response.json(),
            "recent_anomalies": anomalies
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/setup-superset")
async def setup_superset_endpoint() -> JSONResponse:
    try:
        session = requests.Session()
        superset_login(session)
        superset_get_csrf(session)
        db_id = superset_create_db(session)
        datasets = [
            "mart_daily_kpis",
            "mart_rfm",
            "mart_country_performance",
            "mart_product_performance",
            "mart_monthly_trends",
            "ml_forecast_daily",
            "ml_anomalies_daily",
            "v_forecast_vs_actual",
            "v_active_alerts",
            "v_model_performance",
            "fact_sales",
            "dim_date",
            "dim_customer",
            "dim_product",
            "dim_country"
        ]
        for table in datasets:
            superset_create_dataset(session, db_id, table)
        return JSONResponse({
            "status": "success",
            "database_id": db_id,
            "datasets": datasets
        })
    except Exception as exc:
        logger.error("Superset setup failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/create-dashboards")
async def create_dashboards_endpoint() -> JSONResponse:
    """Automatically create all Superset dashboards and charts"""
    try:
        logger.info("Starting automated dashboard creation...")
        result = automate_superset_dashboards(
            SUPERSET_URL,
            SUPERSET_USERNAME,
            SUPERSET_PASSWORD
        )
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
        
        return JSONResponse(result)
    except Exception as exc:
        logger.error("Dashboard automation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/create-forecast-dataset")
async def create_forecast_dataset_endpoint() -> JSONResponse:
    """Create virtual dataset for forecast vs actual visualization"""
    try:
        from superset_automation import SupersetAPI
        
        # SQL query combining historical and forecast data
        sql_query = """
        SELECT 
            full_date as date,
            total_revenue as value,
            'Actual' as type
        FROM mart_daily_kpis
        WHERE full_date >= CURRENT_DATE - INTERVAL '30 days'

        UNION ALL

        SELECT 
            forecast_date as date,
            predicted_value as value,
            'Forecast' as type
        FROM ml_forecast_daily
        WHERE metric_name = 'total_revenue'
            AND forecast_date >= CURRENT_DATE

        ORDER BY date
        """
        
        api = SupersetAPI(SUPERSET_URL, SUPERSET_USERNAME, SUPERSET_PASSWORD)
        dataset_id = api.create_virtual_dataset(
            dataset_name="revenue_actual_vs_forecast",
            sql_query=sql_query
        )
        
        if dataset_id:
            return JSONResponse({
                "status": "success",
                "dataset_id": dataset_id,
                "dataset_name": "revenue_actual_vs_forecast",
                "message": "Virtual dataset created successfully. Go to Charts -> + Chart -> Select 'revenue_actual_vs_forecast' dataset"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to create virtual dataset")
            
    except Exception as exc:
        logger.error("Failed to create forecast dataset: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/backtest")
async def backtest(request: BacktestRequest) -> JSONResponse:
    try:
        url = f"{ML_SERVICE_URL.rstrip('/')}/backtest/{request.metric}"
        params = {"model": request.model, "test_days": request.test_days}
        response = requests.post(url, params=params, timeout=120)
        if response.status_code >= 400:
            raise HTTPException(status_code=500, detail=response.text)
        return JSONResponse({"status": "success", "result": response.json()})
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/queries")
async def list_queries() -> Dict[str, Any]:
    return {
        "queries": [
            {"key": key, "title": value["title"]}
            for key, value in QUERY_LIBRARY.items()
        ]
    }


@app.get("/api/query/{query_key}")
async def run_named_query(query_key: str) -> JSONResponse:
    query = QUERY_LIBRARY.get(query_key)
    if not query:
        raise HTTPException(status_code=404, detail="Unknown query")
    try:
        rows = run_query(query["sql"])
        return JSONResponse({"status": "success", "title": query["title"], "rows": rows})
    except Exception as exc:
        logger.error("Query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/forecasts/latest")
async def forecasts_latest() -> JSONResponse:
    try:
        response = requests.get(f"{ML_SERVICE_URL.rstrip('/')}/forecasts/latest", timeout=30)
        if response.status_code >= 400:
            raise HTTPException(status_code=500, detail=response.text)
        return JSONResponse({"status": "success", "rows": response.json()})
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/anomalies/latest")
async def anomalies_latest() -> JSONResponse:
    try:
        response = requests.get(f"{ML_SERVICE_URL.rstrip('/')}/anomalies/latest", timeout=30)
        if response.status_code >= 400:
            raise HTTPException(status_code=500, detail=response.text)
        return JSONResponse({"status": "success", "rows": response.json()})
    except requests.RequestException as exc:
        raise HTTPException(status_code=500, detail=str(exc))
