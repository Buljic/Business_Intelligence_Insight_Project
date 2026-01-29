"""
E-Commerce ML Microservice
Provides forecasting and anomaly detection for daily KPIs

Enhanced with:
- Backtesting and evaluation metrics (MAPE, SMAPE, baseline comparison)
- Model run tracking for reproducibility
- Improved anomaly detection with seasonality awareness
- Idempotent database operations
"""

import os
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from prophet import Prophet
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.holtwinters import ExponentialSmoothing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service version for tracking
SERVICE_VERSION = "2.0.0"
CODE_VERSION = "2024.01.1"

VALID_METRICS = [
    "total_revenue",
    "total_orders",
    "unique_customers",
    "avg_order_value",
    "total_items_sold"
]
FORECAST_MODELS = {
    "prophet": "Prophet",
    "ets": "ETS"
}
DEFAULT_FORECAST_MODEL = "auto"

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres123@localhost:5432/ecommerce_dw")
engine = create_engine(DATABASE_URL)

app = FastAPI(
    title="E-Commerce ML Service",
    description="Forecasting and Anomaly Detection for E-Commerce KPIs with Backtesting",
    version=SERVICE_VERSION
)

# ============================================
# Pydantic Models
# ============================================

class ForecastRequest(BaseModel):
    metric: str = "total_revenue"
    forecast_days: int = 14
    model: str = DEFAULT_FORECAST_MODEL
    
class ForecastResponse(BaseModel):
    metric: str
    forecasts: List[dict]
    model_name: str
    model_version: str
    created_at: datetime

class AnomalyRequest(BaseModel):
    metric: str = "total_revenue"
    lookback_days: int = 30
    contamination: float = 0.1

class AnomalyResponse(BaseModel):
    metric: str
    anomalies: List[dict]
    total_checked: int
    anomalies_found: int
    created_at: datetime

class TrainResponse(BaseModel):
    status: str
    metrics_trained: List[str]
    forecasts_generated: int
    anomalies_detected: int
    report_path: Optional[str]
    model_selection: Optional[Dict[str, str]] = None

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    last_data_date: Optional[str]
    total_records: int

class BacktestResult(BaseModel):
    metric: str
    model_type: str
    mape: float
    smape: float
    rmse: float
    mae: float
    baseline_mape: float
    improvement_pct: float
    test_samples: int

class ModelRunResponse(BaseModel):
    run_id: int
    model_type: str
    target_metric: str
    mape: float
    baseline_mape: float
    improvement_pct: float
    status: str

# ============================================
# Evaluation Metrics
# ============================================

def calculate_mape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Percentage Error"""
    mask = actual != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)

def calculate_smape(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Symmetric Mean Absolute Percentage Error"""
    denominator = (np.abs(actual) + np.abs(predicted)) / 2
    mask = denominator != 0
    if not mask.any():
        return 0.0
    return float(np.mean(np.abs(actual[mask] - predicted[mask]) / denominator[mask]) * 100)

def calculate_rmse(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Root Mean Square Error"""
    return float(np.sqrt(np.mean((actual - predicted) ** 2)))

def calculate_mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    """Mean Absolute Error"""
    return float(np.mean(np.abs(actual - predicted)))

def naive_baseline_forecast(train: pd.Series, horizon: int) -> np.ndarray:
    """Naive baseline: last week's values = this week's forecast"""
    if len(train) < 7:
        return np.array([train.mean()] * horizon)
    return np.array([train.iloc[-(7 - i % 7)] for i in range(horizon)])

# ============================================
# Helper Functions
# ============================================

def normalize_model_name(model: Optional[str]) -> str:
    """Normalize and validate model name."""
    if not model:
        return DEFAULT_FORECAST_MODEL
    model_key = model.strip().lower()
    if model_key == DEFAULT_FORECAST_MODEL:
        return model_key
    if model_key not in FORECAST_MODELS:
        raise ValueError(f"Invalid model. Choose from: {list(FORECAST_MODELS.keys()) + [DEFAULT_FORECAST_MODEL]}")
    return model_key

def prepare_metric_series(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Ensure daily continuity for time-series models."""
    metric_df = df[['ds', metric]].dropna().copy()
    metric_df = metric_df.set_index('ds').sort_index()
    metric_df = metric_df.asfreq('D')
    metric_df[metric] = metric_df[metric].fillna(0)
    return metric_df.reset_index()

def get_daily_kpis(metric: str = None) -> pd.DataFrame:
    """Fetch daily KPIs from database"""
    query = """
        SELECT full_date as ds, total_revenue, total_orders, 
               unique_customers, avg_order_value, total_items_sold
        FROM mart_daily_kpis 
        ORDER BY full_date
    """
    df = pd.read_sql(query, engine)
    df['ds'] = pd.to_datetime(df['ds'])
    return df

def train_prophet_model(df: pd.DataFrame, metric: str) -> Prophet:
    """Train Prophet model for a specific metric"""
    train_df = df[['ds', metric]].rename(columns={metric: 'y'})
    train_df = train_df.dropna()
    
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10
    )
    model.fit(train_df)
    return model

def train_ets_model(series: pd.Series) -> ExponentialSmoothing:
    """Train ETS model for a specific metric series."""
    model = ExponentialSmoothing(
        series,
        trend="add",
        seasonal="add",
        seasonal_periods=7,
        initialization_method="estimated"
    )
    return model.fit(optimized=True)

def build_forecast_records(dates: List[pd.Timestamp], predicted: np.ndarray,
                           lower: np.ndarray, upper: np.ndarray) -> List[dict]:
    """Normalize forecast outputs into API/DB-ready dicts."""
    records = []
    for idx, date in enumerate(dates):
        records.append({
            "date": date.strftime('%Y-%m-%d'),
            "predicted": round(max(0, float(predicted[idx])), 2),
            "lower_bound": round(max(0, float(lower[idx])), 2),
            "upper_bound": round(max(0, float(upper[idx])), 2)
        })
    return records

def forecast_with_model(df: pd.DataFrame, metric: str, model_type: str, forecast_days: int) -> Tuple[List[dict], dict]:
    """Train selected model and return forecast records + parameters."""
    prepared = prepare_metric_series(df, metric)
    if prepared.empty:
        raise ValueError("No data available for forecasting")

    model_params = {}
    if model_type == "prophet":
        model = train_prophet_model(prepared, metric)
        future = model.make_future_dataframe(periods=forecast_days, freq='D')
        forecast = model.predict(future)
        last_date = prepared['ds'].max()
        future_forecast = forecast[forecast['ds'] > last_date]
        records = build_forecast_records(
            future_forecast['ds'].tolist(),
            future_forecast['yhat'].values,
            future_forecast['yhat_lower'].values,
            future_forecast['yhat_upper'].values
        )
        model_params = {
            "yearly_seasonality": True,
            "weekly_seasonality": True,
            "changepoint_prior_scale": 0.05,
            "seasonality_prior_scale": 10
        }
        return records, model_params

    if model_type == "ets":
        series = prepared.set_index('ds')[metric]
        if len(series) < 14:
            raise ValueError("Insufficient data for ETS forecasting (need at least 14 days).")
        fit = train_ets_model(series)
        forecast_index = pd.date_range(series.index.max() + timedelta(days=1), periods=forecast_days, freq='D')
        forecast = fit.forecast(forecast_days)
        residuals = (series - fit.fittedvalues).dropna()
        resid_std = float(np.std(residuals)) if not residuals.empty else 0.0
        lower = forecast - (1.96 * resid_std)
        upper = forecast + (1.96 * resid_std)
        records = build_forecast_records(
            forecast_index.tolist(),
            forecast.values,
            lower.values,
            upper.values
        )
        model_params = {
            "trend": "add",
            "seasonal": "add",
            "seasonal_periods": 7
        }
        return records, model_params

    raise ValueError(f"Unsupported model: {model_type}")

def detect_anomalies_enhanced(df: pd.DataFrame, metric: str, contamination: float = 0.1) -> pd.DataFrame:
    """
    Enhanced anomaly detection with seasonality awareness.
    Uses forecast residuals for better anomaly identification.
    """
    data = df[[metric]].dropna().copy()
    
    if len(data) < 14:
        return pd.DataFrame()
    
    # Add day of week for seasonality
    data['day_of_week'] = data.index.dayofweek
    data['is_weekend'] = data['day_of_week'].isin([5, 6])
    
    # Calculate seasonality-aware expected values
    # Separate weekend/weekday baselines
    weekend_mean = data[data['is_weekend']][metric].mean()
    weekday_mean = data[~data['is_weekend']][metric].mean()
    data['baseline'] = data['is_weekend'].apply(lambda x: weekend_mean if x else weekday_mean)
    
    # Calculate rolling statistics by day type
    data['rolling_mean'] = data.groupby('is_weekend')[metric].transform(
        lambda x: x.rolling(window=4, min_periods=2).mean()
    )
    data['rolling_std'] = data.groupby('is_weekend')[metric].transform(
        lambda x: x.rolling(window=4, min_periods=2).std()
    )
    
    # Use rolling mean as expected, fall back to day-type baseline
    data['expected'] = data['rolling_mean'].fillna(data['baseline'])
    data['std'] = data['rolling_std'].fillna(data[metric].std())
    
    # Calculate z-score for anomaly detection
    data['z_score'] = (data[metric] - data['expected']) / data['std'].replace(0, 1)
    data['deviation_pct'] = ((data[metric] - data['expected']) / data['expected'].replace(0, 1) * 100).round(2)
    
    # Isolation Forest on residuals (deseasonalized data)
    residuals = (data[metric] - data['expected']).values.reshape(-1, 1)
    model = IsolationForest(contamination=contamination, random_state=42)
    data['if_anomaly'] = model.fit_predict(residuals) == -1
    
    # Combined anomaly detection: IF + z-score threshold
    data['is_anomaly'] = data['if_anomaly'] | (data['z_score'].abs() > 2.5)
    
    # Determine anomaly type
    data['anomaly_type'] = data.apply(
        lambda x: 'spike' if x['is_anomaly'] and x[metric] > x['expected'] 
                  else 'drop' if x['is_anomaly'] and x[metric] < x['expected']
                  else None, 
        axis=1
    )
    
    # Determine severity based on z-score and deviation
    def get_severity(row):
        z = abs(row['z_score'])
        dev = abs(row['deviation_pct'])
        if z > 4 or dev > 50:
            return 'critical'
        elif z > 3 or dev > 30:
            return 'high'
        elif z > 2 or dev > 15:
            return 'medium'
        return 'low'
    
    data['severity'] = data.apply(get_severity, axis=1)
    
    # Generate business interpretation
    def get_interpretation(row):
        if not row['is_anomaly']:
            return None
        day_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][row['day_of_week']]
        if row['anomaly_type'] == 'spike':
            if row['is_weekend']:
                return f"Unusual weekend spike on {day_name}. Possible promotion effect or special event."
            return f"Unexpected high {metric.replace('_', ' ')} on {day_name}. Review for campaign impact."
        else:
            if row['is_weekend']:
                return f"Weekend drop on {day_name} below normal patterns. Check for site issues."
            return f"Weekday underperformance on {day_name}. Investigate operational issues."
    
    data['business_interpretation'] = data.apply(get_interpretation, axis=1)
    
    # Add recommended action
    def get_action(row):
        if not row['is_anomaly']:
            return None
        if row['severity'] in ['critical', 'high']:
            if row['anomaly_type'] == 'drop':
                return "URGENT: Check website uptime, payment systems, and inventory availability."
            return "Review: Identify cause of spike for replication or concern."
        return "Monitor: Track if pattern continues over next few days."
    
    data['recommended_action'] = data.apply(get_action, axis=1)
    
    result = data[data['is_anomaly']].copy()
    return result

def save_forecasts_to_db(forecasts: List[dict], metric: str, model_name: str,
                         model_version: str, model_run_id: Optional[int] = None):
    """Save forecast results to database"""
    with engine.connect() as conn:
        for f in forecasts:
            conn.execute(text("""
                INSERT INTO ml_forecast_daily (forecast_date, metric_name, predicted_value, 
                                               lower_bound, upper_bound, model_run_id,
                                               model_name, model_version)
                VALUES (:date, :metric, :predicted, :lower, :upper, :run_id, :model, :version)
                ON CONFLICT (forecast_date, metric_name) 
                DO UPDATE SET predicted_value = :predicted, lower_bound = :lower, 
                              upper_bound = :upper, model_run_id = :run_id,
                              model_name = :model, model_version = :version,
                              updated_at = CURRENT_TIMESTAMP
            """), {
                "date": f["date"],
                "metric": metric,
                "predicted": f["predicted"],
                "lower": f["lower_bound"],
                "upper": f["upper_bound"],
                "model": model_name,
                "version": model_version,
                "run_id": model_run_id
            })
        conn.commit()

def save_anomalies_to_db(anomalies: List[dict], metric: str, run_id: int = None):
    """Save anomaly results to database with upsert for idempotency"""
    with engine.connect() as conn:
        for a in anomalies:
            conn.execute(text("""
                INSERT INTO ml_anomalies_daily (
                    anomaly_date, metric_name, actual_value, expected_value, 
                    deviation_pct, z_score, anomaly_type, severity,
                    is_weekend, day_of_week, business_interpretation, 
                    recommended_action, model_run_id
                )
                VALUES (
                    :date, :metric, :actual, :expected, :deviation, :z_score,
                    :type, :severity, :is_weekend, :dow, :interpretation, 
                    :action, :run_id
                )
                ON CONFLICT (anomaly_date, metric_name) 
                DO UPDATE SET 
                    actual_value = :actual,
                    expected_value = :expected,
                    deviation_pct = :deviation,
                    z_score = :z_score,
                    anomaly_type = :type,
                    severity = :severity,
                    business_interpretation = :interpretation,
                    recommended_action = :action,
                    model_run_id = :run_id,
                    updated_at = CURRENT_TIMESTAMP
            """), {
                "date": a["date"],
                "metric": metric,
                "actual": a["actual"],
                "expected": a["expected"],
                "deviation": a.get("deviation_pct", 0),
                "z_score": a.get("z_score", 0),
                "type": a["anomaly_type"],
                "severity": a["severity"],
                "is_weekend": a.get("is_weekend", False),
                "dow": a.get("day_of_week", 0),
                "interpretation": a.get("business_interpretation"),
                "action": a.get("recommended_action"),
                "run_id": run_id
            })
        conn.commit()

def save_model_run(model_type: str, metric: str, train_start: str, train_end: str,
                   train_samples: int, params: dict, mape: Optional[float], smape: Optional[float],
                   rmse: Optional[float], mae: Optional[float], baseline_mape: Optional[float],
                   baseline_rmse: Optional[float]) -> int:
    """Record model training run for reproducibility"""
    def safe_round(value: Optional[float], digits: int = 4) -> Optional[float]:
        return round(value, digits) if value is not None else None

    if baseline_mape is not None and mape is not None and baseline_mape > 0:
        improvement = ((baseline_mape - mape) / baseline_mape * 100)
    else:
        improvement = None
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO ml_model_runs (
                model_type, target_metric, train_start_date, train_end_date,
                train_samples, parameters, mape, smape, rmse, mae,
                baseline_mape, baseline_rmse, improvement_vs_baseline_pct,
                model_version, code_version, status
            ) VALUES (
                :model_type, :metric, :train_start, :train_end, :samples,
                :params, :mape, :smape, :rmse, :mae, :baseline_mape, :baseline_rmse,
                :improvement, :model_version, :code_version, 'completed'
            )
            RETURNING run_id
        """), {
            "model_type": model_type,
            "metric": metric,
            "train_start": train_start,
            "train_end": train_end,
            "samples": train_samples,
            "params": json.dumps(params),
            "mape": safe_round(mape),
            "smape": safe_round(smape),
            "rmse": safe_round(rmse),
            "mae": safe_round(mae),
            "baseline_mape": safe_round(baseline_mape),
            "baseline_rmse": safe_round(baseline_rmse),
            "improvement": safe_round(improvement),
            "model_version": SERVICE_VERSION,
            "code_version": CODE_VERSION
        })
        run_id = result.fetchone()[0]
        conn.commit()
        return run_id

def backtest_model(df: pd.DataFrame, metric: str, model_type: str, test_days: int = 14) -> Dict:
    """
    Perform time-series backtest for a specific model.
    Returns evaluation metrics and comparison vs naive baseline.
    """
    prepared = prepare_metric_series(df, metric)
    if len(prepared) < test_days + 30:
        raise ValueError(f"Insufficient data for backtesting. Need at least {test_days + 30} days.")

    train_df = prepared.iloc[:-test_days].copy()
    test_df = prepared.iloc[-test_days:].copy()
    actuals = test_df[metric].values

    if model_type == "prophet":
        prophet_train = train_df[['ds', metric]].rename(columns={metric: 'y'})
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05
        )
        model.fit(prophet_train)
        future = model.make_future_dataframe(periods=test_days, freq='D')
        forecast = model.predict(future)
        predictions = forecast.iloc[-test_days:]['yhat'].values
    elif model_type == "ets":
        series = train_df.set_index('ds')[metric]
        fit = train_ets_model(series)
        predictions = fit.forecast(test_days).values
    else:
        raise ValueError(f"Unsupported model: {model_type}")

    predictions = np.clip(predictions, 0, None)

    baseline_preds = naive_baseline_forecast(train_df[metric], test_days)
    baseline_rmse = calculate_rmse(actuals, baseline_preds)

    mape = calculate_mape(actuals, predictions)
    smape = calculate_smape(actuals, predictions)
    rmse = calculate_rmse(actuals, predictions)
    mae = calculate_mae(actuals, predictions)
    baseline_mape = calculate_mape(actuals, baseline_preds)

    improvement = ((baseline_mape - mape) / baseline_mape * 100) if baseline_mape > 0 else 0

    return {
        "metric": metric,
        "model_type": model_type,
        "mape": round(mape, 2),
        "smape": round(smape, 2),
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "baseline_mape": round(baseline_mape, 2),
        "baseline_rmse": round(baseline_rmse, 2),
        "improvement_pct": round(improvement, 2),
        "test_samples": test_days,
        "train_start": str(train_df['ds'].min().date()),
        "train_end": str(train_df['ds'].max().date()),
        "predictions": predictions.tolist(),
        "actuals": actuals.tolist()
    }

def select_best_model(df: pd.DataFrame, metric: str, test_days: int = 14) -> Tuple[str, List[Dict]]:
    """Evaluate candidate models and select the best by MAPE."""
    results = []
    for model_type in FORECAST_MODELS.keys():
        try:
            result = backtest_model(df, metric, model_type, test_days)
            results.append(result)
        except Exception as exc:
            logger.warning(f"Backtest failed for {metric} with {model_type}: {exc}")
    if not results:
        raise ValueError("No valid models available for selection")
    best = sorted(results, key=lambda x: x["mape"])[0]
    return best["model_type"], results

def generate_report(forecasts: dict, anomalies: dict, report_path: str):
    """Generate markdown report for anomalies and forecasts"""
    report_lines = [
        "# E-Commerce ML Analysis Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Executive Summary\n"
    ]
    
    # Forecast summary
    report_lines.append("### Revenue Forecast (Next 14 Days)\n")
    if "total_revenue" in forecasts and 14 in forecasts["total_revenue"]:
        for f in forecasts["total_revenue"][14][:14]:
            report_lines.append(f"- **{f['date']}**: ${f['predicted']:,.2f} (range: ${f['lower_bound']:,.2f} - ${f['upper_bound']:,.2f})")
    
    report_lines.append("\n### Orders Forecast (Next 14 Days)\n")
    if "total_orders" in forecasts and 14 in forecasts["total_orders"]:
        for f in forecasts["total_orders"][14][:14]:
            report_lines.append(f"- **{f['date']}**: {int(f['predicted'])} orders (range: {int(f['lower_bound'])} - {int(f['upper_bound'])})")

    # Yearly strategic summary
    if "total_revenue" in forecasts and 365 in forecasts["total_revenue"]:
        forecast_year_revenue = sum(f["predicted"] for f in forecasts["total_revenue"][365])
        forecast_year_orders = None
        if "total_orders" in forecasts and 365 in forecasts["total_orders"]:
            forecast_year_orders = sum(f["predicted"] for f in forecasts["total_orders"][365])

        try:
            with engine.connect() as conn:
                actuals = conn.execute(text("""
                    SELECT
                        SUM(total_revenue) as revenue,
                        SUM(total_orders) as orders
                    FROM mart_daily_kpis
                    WHERE full_date >= (SELECT MAX(full_date) - INTERVAL '365 days' FROM mart_daily_kpis)
                """)).fetchone()
            actual_year_revenue = float(actuals[0] or 0)
            actual_year_orders = float(actuals[1] or 0)
        except Exception as exc:
            logger.warning(f"Failed to compute yearly actuals: {exc}")
            actual_year_revenue = 0
            actual_year_orders = 0

        report_lines.append("\n### Yearly Strategic Outlook (Next 365 Days)\n")
        report_lines.append(f"- **Forecast Revenue (365d):** ${forecast_year_revenue:,.0f}")
        if actual_year_revenue > 0:
            delta_rev = forecast_year_revenue - actual_year_revenue
            delta_rev_pct = (delta_rev / actual_year_revenue) * 100
            report_lines.append(f"- **Last 365d Revenue:** ${actual_year_revenue:,.0f}")
            report_lines.append(f"- **Delta vs Last Year:** ${delta_rev:,.0f} ({delta_rev_pct:+.1f}%)")
        if forecast_year_orders is not None:
            report_lines.append(f"- **Forecast Orders (365d):** {forecast_year_orders:,.0f}")
            if actual_year_orders > 0:
                delta_ord = forecast_year_orders - actual_year_orders
                delta_ord_pct = (delta_ord / actual_year_orders) * 100
                report_lines.append(f"- **Last 365d Orders:** {actual_year_orders:,.0f}")
                report_lines.append(f"- **Delta vs Last Year:** {delta_ord:,.0f} ({delta_ord_pct:+.1f}%)")
    
    # Anomaly summary
    report_lines.append("\n---\n")
    report_lines.append("## Anomaly Detection Results\n")
    
    total_anomalies = sum(len(v) for v in anomalies.values())
    report_lines.append(f"**Total Anomalies Detected:** {total_anomalies}\n")
    
    for metric, anoms in anomalies.items():
        if anoms:
            report_lines.append(f"\n### {metric.replace('_', ' ').title()} Anomalies\n")
            report_lines.append("| Date | Actual | Expected | Deviation | Type | Severity |")
            report_lines.append("|------|--------|----------|-----------|------|----------|")
            for a in anoms:
                report_lines.append(
                    f"| {a['date']} | {a['actual']:,.2f} | {a['expected']:,.2f} | "
                    f"{a['deviation_pct']:+.1f}% | {a['anomaly_type']} | {a['severity']} |"
                )
    
    # Alerts section
    critical_anomalies = [a for anoms in anomalies.values() for a in anoms if a['severity'] == 'critical']
    if critical_anomalies:
        report_lines.append("\n---\n")
        report_lines.append("## ⚠️ CRITICAL ALERTS\n")
        for a in critical_anomalies:
            report_lines.append(f"- **{a['date']}**: {a['anomaly_type'].upper()} in metric detected!")
            report_lines.append(f"  - Actual: {a['actual']:,.2f}, Expected: {a['expected']:,.2f}")
            report_lines.append(f"  - Deviation: {a['deviation_pct']:+.1f}%\n")
    
    report_lines.append("\n---\n")
    report_lines.append(f"*Report generated by E-Commerce ML Service v{SERVICE_VERSION}*")
    
    # Write report
    with open(report_path, 'w') as f:
        f.write('\n'.join(report_lines))
    
    logger.info(f"Report saved to {report_path}")

# ============================================
# API Endpoints
# ============================================

@app.get("/", response_model=dict)
async def root():
    """API root endpoint"""
    return {
        "service": "E-Commerce ML Service",
        "version": SERVICE_VERSION,
        "endpoints": ["/health", "/forecast", "/anomalies", "/train", "/backtest/{metric}"]
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check service health and database connectivity"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT MAX(full_date) as last_date, COUNT(*) as total FROM mart_daily_kpis"
            )).fetchone()
            
            return HealthResponse(
                status="healthy",
                database_connected=True,
                last_data_date=str(result[0]) if result[0] else None,
                total_records=result[1] or 0
            )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            database_connected=False,
            last_data_date=None,
            total_records=0
        )

@app.post("/forecast", response_model=ForecastResponse)
async def generate_forecast(request: ForecastRequest):
    """Generate forecast for a specific metric"""
    if request.metric not in VALID_METRICS:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {VALID_METRICS}")

    try:
        df = get_daily_kpis()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for forecasting")

        try:
            model_choice = normalize_model_name(request.model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        backtest_result = None

        if model_choice == DEFAULT_FORECAST_MODEL:
            model_choice, candidates = select_best_model(df, request.metric)
            backtest_result = next(r for r in candidates if r["model_type"] == model_choice)
        else:
            backtest_result = backtest_model(df, request.metric, model_choice)

        forecasts, model_params = forecast_with_model(df, request.metric, model_choice, request.forecast_days)
        prepared = prepare_metric_series(df, request.metric)

        run_id = save_model_run(
            model_type=f"forecast_{model_choice}",
            metric=request.metric,
            train_start=str(prepared['ds'].min().date()),
            train_end=str(prepared['ds'].max().date()),
            train_samples=len(prepared),
            params=model_params,
            mape=backtest_result["mape"],
            smape=backtest_result["smape"],
            rmse=backtest_result["rmse"],
            mae=backtest_result["mae"],
            baseline_mape=backtest_result["baseline_mape"],
            baseline_rmse=backtest_result["baseline_rmse"]
        )

        save_forecasts_to_db(
            forecasts,
            request.metric,
            model_name=FORECAST_MODELS[model_choice],
            model_version=SERVICE_VERSION,
            model_run_id=run_id
        )

        return ForecastResponse(
            metric=request.metric,
            forecasts=forecasts,
            model_name=FORECAST_MODELS[model_choice],
            model_version=SERVICE_VERSION,
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/anomalies", response_model=AnomalyResponse)
async def detect_anomalies_endpoint(request: AnomalyRequest):
    """Detect anomalies in a specific metric"""
    valid_metrics = ["total_revenue", "total_orders", "unique_customers", "avg_order_value"]

    if request.metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {valid_metrics}")
    
    try:
        df = get_daily_kpis()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for anomaly detection")
        
        # Filter to lookback period
        cutoff_date = df['ds'].max() - timedelta(days=request.lookback_days)
        df_recent = df[df['ds'] >= cutoff_date].copy()
        df_recent = df_recent.set_index('ds')
        
        anomaly_df = detect_anomalies_enhanced(df_recent, request.metric, request.contamination)
        
        anomalies = []
        for date, row in anomaly_df.iterrows():
            anomalies.append({
                "date": date.strftime('%Y-%m-%d'),
                "actual": round(row[request.metric], 2),
                "expected": round(row['expected'], 2),
                "deviation_pct": row['deviation_pct'],
                "anomaly_type": row['anomaly_type'],
                "severity": row['severity']
            })
        
        # Save to database
        if anomalies:
            save_anomalies_to_db(anomalies, request.metric)
        
        return AnomalyResponse(
            metric=request.metric,
            anomalies=anomalies,
            total_checked=len(df_recent),
            anomalies_found=len(anomalies),
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Anomaly detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/train", response_model=TrainResponse)
async def train_all_models(background_tasks: BackgroundTasks):
    """Train models for all metrics, generate forecasts, detect anomalies, and create report"""
    metrics = ["total_revenue", "total_orders"]
    
    try:
        df = get_daily_kpis()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for training")
        
        all_forecasts = {}
        all_anomalies = {}
        model_selection = {}
        total_forecasts = 0
        total_anomalies = 0
        forecast_horizons = [14, 365]
        
        for metric in metrics:
            logger.info(f"Selecting best model for {metric}")
            best_model, candidates = select_best_model(df, metric)
            model_selection[metric] = best_model
            backtest_result = next(r for r in candidates if r["model_type"] == best_model)

            logger.info(f"Training {best_model} model for {metric}")
            metric_forecasts = {}
            model_params = {}
            for horizon in forecast_horizons:
                forecasts, model_params = forecast_with_model(df, metric, best_model, horizon)
                metric_forecasts[horizon] = forecasts
            prepared = prepare_metric_series(df, metric)

            run_id = save_model_run(
                model_type=f"forecast_{best_model}",
                metric=metric,
                train_start=str(prepared['ds'].min().date()),
                train_end=str(prepared['ds'].max().date()),
                train_samples=len(prepared),
                params=model_params,
                mape=backtest_result["mape"],
                smape=backtest_result["smape"],
                rmse=backtest_result["rmse"],
                mae=backtest_result["mae"],
                baseline_mape=backtest_result["baseline_mape"],
                baseline_rmse=backtest_result["baseline_rmse"]
            )

            all_forecasts[metric] = metric_forecasts
            for horizon, horizon_forecasts in metric_forecasts.items():
                save_forecasts_to_db(
                    horizon_forecasts,
                    metric,
                    model_name=FORECAST_MODELS[best_model],
                    model_version=SERVICE_VERSION,
                    model_run_id=run_id
                )
                total_forecasts += len(horizon_forecasts)

            logger.info(f"Detecting anomalies for {metric}")
            df_indexed = df.set_index('ds')
            anomaly_df = detect_anomalies_enhanced(df_indexed, metric)

            anomalies = []
            for date, row in anomaly_df.iterrows():
                anomalies.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "actual": round(row[metric], 2),
                    "expected": round(row['expected'], 2),
                    "deviation_pct": row['deviation_pct'],
                    "anomaly_type": row['anomaly_type'],
                    "severity": row['severity']
                })

            all_anomalies[metric] = anomalies
            if anomalies:
                anomaly_run_id = save_model_run(
                    model_type="anomaly_isolation_forest",
                    metric=metric,
                    train_start=str(df['ds'].min().date()),
                    train_end=str(df['ds'].max().date()),
                    train_samples=len(df),
                    params={"contamination": 0.1},
                    mape=None,
                    smape=None,
                    rmse=None,
                    mae=None,
                    baseline_mape=None,
                    baseline_rmse=None
                )
                save_anomalies_to_db(anomalies, metric, run_id=anomaly_run_id)
            total_anomalies += len(anomalies)
        
        # Generate report
        report_path = f"/reports/ml_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        generate_report(all_forecasts, all_anomalies, report_path)
        
        return TrainResponse(
            status="success",
            metrics_trained=metrics,
            forecasts_generated=total_forecasts,
            anomalies_detected=total_anomalies,
            report_path=report_path,
            model_selection=model_selection
        )
        
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/forecasts/latest", response_model=List[dict])
async def get_latest_forecasts():
    """Get latest forecasts from database"""
    try:
        query = """
            SELECT forecast_date, metric_name, predicted_value, 
                   lower_bound, upper_bound, model_name, created_at
            FROM ml_forecast_daily
            WHERE forecast_date >= CURRENT_DATE
            ORDER BY metric_name, forecast_date
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anomalies/latest", response_model=List[dict])
async def get_latest_anomalies():
    """Get latest detected anomalies from database"""
    try:
        query = """
            SELECT anomaly_date, metric_name, actual_value, expected_value,
                   deviation_pct, anomaly_type, severity, 
                   business_interpretation, recommended_action,
                   is_weekend, acknowledged, created_at
            FROM ml_anomalies_daily
            ORDER BY anomaly_date DESC, 
                     CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 
                          WHEN 'medium' THEN 3 ELSE 4 END
            LIMIT 50
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/anomalies/active", response_model=List[dict])
async def get_active_alerts():
    """Get unacknowledged anomalies requiring attention"""
    try:
        query = """
            SELECT anomaly_date, metric_name, actual_value, expected_value,
                   deviation_pct, anomaly_type, severity,
                   business_interpretation, recommended_action
            FROM ml_anomalies_daily
            WHERE NOT acknowledged
              AND anomaly_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 
                          WHEN 'medium' THEN 3 ELSE 4 END,
                     anomaly_date DESC
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/backtest/{metric}", response_model=BacktestResult)
async def run_backtest(metric: str, test_days: int = 14, model: str = DEFAULT_FORECAST_MODEL):
    """Run backtest for a specific metric and return evaluation metrics"""
    valid_metrics = ["total_revenue", "total_orders"]

    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {valid_metrics}")

    try:
        df = get_daily_kpis()

        if len(df) < test_days + 30:
            raise HTTPException(status_code=400,
                detail=f"Insufficient data. Need at least {test_days + 30} days, have {len(df)}.")

        try:
            model_choice = normalize_model_name(model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        if model_choice == DEFAULT_FORECAST_MODEL:
            model_choice, candidates = select_best_model(df, metric, test_days)
            result = next(r for r in candidates if r["model_type"] == model_choice)
        else:
            result = backtest_model(df, metric, model_choice, test_days)

        return BacktestResult(
            metric=result["metric"],
            model_type=result["model_type"],
            mape=result["mape"],
            smape=result["smape"],
            rmse=result["rmse"],
            mae=result["mae"],
            baseline_mape=result["baseline_mape"],
            improvement_pct=result["improvement_pct"],
            test_samples=result["test_samples"]
        )

    except Exception as e:
        logger.error(f"Backtest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/model-runs", response_model=List[dict])
async def get_model_runs(limit: int = 20):
    """Get recent model training runs"""
    try:
        query = f"""
            SELECT run_id, model_type, target_metric, train_start_date, train_end_date,
                   train_samples, mape, smape, baseline_mape, improvement_vs_baseline_pct,
                   model_version, code_version, run_timestamp, status
            FROM ml_model_runs
            ORDER BY run_timestamp DESC
            LIMIT {limit}
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard/freshness", response_model=List[dict])
async def get_data_freshness():
    """Get data freshness status for all tables (for dashboard 'last updated' display)"""
    try:
        query = """
            SELECT table_name, last_refresh_at, row_count,
                   EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_refresh_at))/3600 as hours_since_refresh,
                   CASE 
                       WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '6 hours' THEN 'fresh'
                       WHEN last_refresh_at > CURRENT_TIMESTAMP - INTERVAL '24 hours' THEN 'stale'
                       ELSE 'outdated'
                   END as freshness_status
            FROM table_refresh_log
            ORDER BY last_refresh_at DESC
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/acknowledge/{anomaly_date}/{metric}")
async def acknowledge_anomaly(anomaly_date: str, metric: str, acknowledged_by: str = "analyst"):
    """Mark an anomaly as acknowledged"""
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE ml_anomalies_daily 
                SET acknowledged = TRUE, 
                    acknowledged_by = :user,
                    acknowledged_at = CURRENT_TIMESTAMP
                WHERE anomaly_date = :date AND metric_name = :metric
            """), {"date": anomaly_date, "metric": metric, "user": acknowledged_by})
            conn.commit()
        return {"status": "acknowledged", "date": anomaly_date, "metric": metric}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
