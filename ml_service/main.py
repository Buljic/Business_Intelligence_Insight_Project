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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service version for tracking
SERVICE_VERSION = "2.0.0"
CODE_VERSION = "2024.01.1"

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
    forecast_days: int = 7
    
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

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    last_data_date: Optional[str]
    total_records: int

class BacktestResult(BaseModel):
    metric: str
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

def save_forecasts_to_db(forecasts: List[dict], metric: str, model_name: str = "Prophet"):
    """Save forecast results to database"""
    with engine.connect() as conn:
        for f in forecasts:
            conn.execute(text("""
                INSERT INTO ml_forecast_daily (forecast_date, metric_name, predicted_value, 
                                               lower_bound, upper_bound, model_name, model_version)
                VALUES (:date, :metric, :predicted, :lower, :upper, :model, :version)
                ON CONFLICT (forecast_date, metric_name) 
                DO UPDATE SET predicted_value = :predicted, lower_bound = :lower, 
                              upper_bound = :upper, created_at = CURRENT_TIMESTAMP
            """), {
                "date": f["date"],
                "metric": metric,
                "predicted": f["predicted"],
                "lower": f["lower_bound"],
                "upper": f["upper_bound"],
                "model": model_name,
                "version": "1.0"
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
                   train_samples: int, params: dict, mape: float, smape: float, 
                   rmse: float, mae: float, baseline_mape: float) -> int:
    """Record model training run for reproducibility"""
    improvement = ((baseline_mape - mape) / baseline_mape * 100) if baseline_mape > 0 else 0
    
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
            "mape": round(mape, 4),
            "smape": round(smape, 4),
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "baseline_mape": round(baseline_mape, 4),
            "baseline_rmse": round(rmse, 4),
            "improvement": round(improvement, 4),
            "model_version": SERVICE_VERSION,
            "code_version": CODE_VERSION
        })
        run_id = result.fetchone()[0]
        conn.commit()
        return run_id

def backtest_model(df: pd.DataFrame, metric: str, test_days: int = 14) -> Dict:
    """
    Perform time-series cross-validation backtest.
    Returns evaluation metrics and comparison vs naive baseline.
    """
    if len(df) < test_days + 30:
        raise ValueError(f"Insufficient data for backtesting. Need at least {test_days + 30} days.")
    
    # Split data
    train_df = df.iloc[:-test_days].copy()
    test_df = df.iloc[-test_days:].copy()
    
    # Train Prophet on training data
    prophet_train = train_df[['ds', metric]].rename(columns={metric: 'y'})
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05
    )
    model.fit(prophet_train)
    
    # Predict on test period
    future = model.make_future_dataframe(periods=test_days)
    forecast = model.predict(future)
    predictions = forecast.iloc[-test_days:]['yhat'].values
    
    # Get actuals
    actuals = test_df[metric].values
    
    # Calculate naive baseline (last week = this week)
    baseline_preds = naive_baseline_forecast(train_df[metric], test_days)
    
    # Calculate metrics
    mape = calculate_mape(actuals, predictions)
    smape = calculate_smape(actuals, predictions)
    rmse = calculate_rmse(actuals, predictions)
    mae = calculate_mae(actuals, predictions)
    baseline_mape = calculate_mape(actuals, baseline_preds)
    
    improvement = ((baseline_mape - mape) / baseline_mape * 100) if baseline_mape > 0 else 0
    
    return {
        "metric": metric,
        "mape": round(mape, 2),
        "smape": round(smape, 2),
        "rmse": round(rmse, 2),
        "mae": round(mae, 2),
        "baseline_mape": round(baseline_mape, 2),
        "improvement_pct": round(improvement, 2),
        "test_samples": test_days,
        "train_start": str(train_df['ds'].min().date()),
        "train_end": str(train_df['ds'].max().date()),
        "predictions": predictions.tolist(),
        "actuals": actuals.tolist()
    }

def generate_report(forecasts: dict, anomalies: dict, report_path: str):
    """Generate markdown report for anomalies and forecasts"""
    report_lines = [
        "# E-Commerce ML Analysis Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n---\n",
        "## Executive Summary\n"
    ]
    
    # Forecast summary
    report_lines.append("### Revenue Forecast (Next 7 Days)\n")
    if "total_revenue" in forecasts:
        for f in forecasts["total_revenue"][:7]:
            report_lines.append(f"- **{f['date']}**: ${f['predicted']:,.2f} (range: ${f['lower_bound']:,.2f} - ${f['upper_bound']:,.2f})")
    
    report_lines.append("\n### Orders Forecast (Next 7 Days)\n")
    if "total_orders" in forecasts:
        for f in forecasts["total_orders"][:7]:
            report_lines.append(f"- **{f['date']}**: {int(f['predicted'])} orders (range: {int(f['lower_bound'])} - {int(f['upper_bound'])})")
    
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
    report_lines.append("*Report generated by E-Commerce ML Service v1.0*")
    
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
        "version": "1.0.0",
        "endpoints": ["/health", "/forecast", "/anomalies", "/train"]
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
    valid_metrics = ["total_revenue", "total_orders", "unique_customers", "avg_order_value", "total_items_sold"]
    
    if request.metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {valid_metrics}")
    
    try:
        df = get_daily_kpis()
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No data available for forecasting")
        
        model = train_prophet_model(df, request.metric)
        
        # Create future dataframe
        future = model.make_future_dataframe(periods=request.forecast_days)
        forecast = model.predict(future)
        
        # Get only future predictions
        last_date = df['ds'].max()
        future_forecast = forecast[forecast['ds'] > last_date]
        
        forecasts = []
        for _, row in future_forecast.iterrows():
            forecasts.append({
                "date": row['ds'].strftime('%Y-%m-%d'),
                "predicted": round(max(0, row['yhat']), 2),
                "lower_bound": round(max(0, row['yhat_lower']), 2),
                "upper_bound": round(max(0, row['yhat_upper']), 2)
            })
        
        # Save to database
        save_forecasts_to_db(forecasts, request.metric)
        
        return ForecastResponse(
            metric=request.metric,
            forecasts=forecasts,
            model_name="Prophet",
            model_version="1.0",
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
        
        anomaly_df = detect_anomalies(df_recent, request.metric, request.contamination)
        
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
        total_forecasts = 0
        total_anomalies = 0
        
        for metric in metrics:
            # Train and forecast
            logger.info(f"Training model for {metric}")
            model = train_prophet_model(df, metric)
            
            future = model.make_future_dataframe(periods=7)
            forecast = model.predict(future)
            
            last_date = df['ds'].max()
            future_forecast = forecast[forecast['ds'] > last_date]
            
            forecasts = []
            for _, row in future_forecast.iterrows():
                forecasts.append({
                    "date": row['ds'].strftime('%Y-%m-%d'),
                    "predicted": round(max(0, row['yhat']), 2),
                    "lower_bound": round(max(0, row['yhat_lower']), 2),
                    "upper_bound": round(max(0, row['yhat_upper']), 2)
                })
            
            all_forecasts[metric] = forecasts
            save_forecasts_to_db(forecasts, metric)
            total_forecasts += len(forecasts)
            
            # Detect anomalies
            logger.info(f"Detecting anomalies for {metric}")
            df_indexed = df.set_index('ds')
            anomaly_df = detect_anomalies(df_indexed, metric)
            
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
                save_anomalies_to_db(anomalies, metric)
            total_anomalies += len(anomalies)
        
        # Generate report
        report_path = f"/reports/ml_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        generate_report(all_forecasts, all_anomalies, report_path)
        
        return TrainResponse(
            status="success",
            metrics_trained=metrics,
            forecasts_generated=total_forecasts,
            anomalies_detected=total_anomalies,
            report_path=report_path
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
async def run_backtest(metric: str, test_days: int = 14):
    """Run backtest for a specific metric and return evaluation metrics"""
    valid_metrics = ["total_revenue", "total_orders"]
    
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric. Choose from: {valid_metrics}")
    
    try:
        df = get_daily_kpis()
        
        if len(df) < test_days + 30:
            raise HTTPException(status_code=400, 
                detail=f"Insufficient data. Need at least {test_days + 30} days, have {len(df)}.")
        
        result = backtest_model(df, metric, test_days)
        
        return BacktestResult(
            metric=result["metric"],
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
