"""
E-Commerce ML Microservice
Provides forecasting and anomaly detection for daily KPIs
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List

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

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres123@localhost:5432/ecommerce_dw")
engine = create_engine(DATABASE_URL)

app = FastAPI(
    title="E-Commerce ML Service",
    description="Forecasting and Anomaly Detection for E-Commerce KPIs",
    version="1.0.0"
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

def detect_anomalies(df: pd.DataFrame, metric: str, contamination: float = 0.1) -> pd.DataFrame:
    """Detect anomalies using Isolation Forest"""
    data = df[[metric]].dropna()
    
    if len(data) < 10:
        return pd.DataFrame()
    
    model = IsolationForest(contamination=contamination, random_state=42)
    data['anomaly'] = model.fit_predict(data[[metric]])
    data['is_anomaly'] = data['anomaly'] == -1
    
    # Calculate expected value (rolling mean)
    data['expected'] = data[metric].rolling(window=7, min_periods=1).mean()
    data['deviation_pct'] = ((data[metric] - data['expected']) / data['expected'] * 100).round(2)
    
    # Determine anomaly type
    data['anomaly_type'] = data.apply(
        lambda x: 'spike' if x[metric] > x['expected'] else 'drop' if x['is_anomaly'] else None, 
        axis=1
    )
    
    # Determine severity
    data['severity'] = data['deviation_pct'].abs().apply(
        lambda x: 'critical' if x > 50 else 'high' if x > 30 else 'medium' if x > 15 else 'low'
    )
    
    return data[data['is_anomaly']]

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

def save_anomalies_to_db(anomalies: List[dict], metric: str):
    """Save anomaly results to database"""
    with engine.connect() as conn:
        for a in anomalies:
            conn.execute(text("""
                INSERT INTO ml_anomalies_daily (anomaly_date, metric_name, actual_value, 
                                                expected_value, deviation_pct, anomaly_type, severity)
                VALUES (:date, :metric, :actual, :expected, :deviation, :type, :severity)
            """), {
                "date": a["date"],
                "metric": metric,
                "actual": a["actual"],
                "expected": a["expected"],
                "deviation": a["deviation_pct"],
                "type": a["anomaly_type"],
                "severity": a["severity"]
            })
        conn.commit()

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
                   deviation_pct, anomaly_type, severity, created_at
            FROM ml_anomalies_daily
            ORDER BY anomaly_date DESC, severity DESC
            LIMIT 50
        """
        df = pd.read_sql(query, engine)
        return df.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
