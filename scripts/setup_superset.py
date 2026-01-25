#!/usr/bin/env python3
"""
Superset Setup Script
Automatically configures Superset with PostgreSQL data source and datasets
Run this after Superset container is up and running
"""

import requests
import json
import time

SUPERSET_URL = "http://localhost:8088"
USERNAME = "admin"
PASSWORD = "admin123"

def get_access_token(session: requests.Session):
    """Get JWT access token from Superset"""
    login_url = f"{SUPERSET_URL}/api/v1/security/login"
    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "provider": "db",
        "refresh": True
    }
    response = session.post(login_url, json=payload)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"Login failed: {response.text}")
        return None

def get_csrf_token(session: requests.Session):
    """Get CSRF token"""
    csrf_url = f"{SUPERSET_URL}/api/v1/security/csrf_token/"
    response = session.get(csrf_url)
    if response.status_code == 200:
        return response.json()["result"]
    return None

def create_database_connection(session: requests.Session):
    """Create PostgreSQL database connection"""
    db_url = f"{SUPERSET_URL}/api/v1/database/"
    
    payload = {
        "database_name": "E-Commerce Data Warehouse",
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
    
    response = session.post(db_url, json=payload)
    if response.status_code in [200, 201]:
        db_id = response.json()["id"]
        print(f"[OK] Database connection created (ID: {db_id})")
        return db_id
    else:
        print(f"Database creation failed: {response.text}")
        # Try to get existing database
        response = session.get(db_url)
        if response.status_code == 200:
            databases = response.json().get("result", [])
            for db in databases:
                if "ecommerce" in db.get("database_name", "").lower():
                    print(f"[OK] Found existing database (ID: {db['id']})")
                    return db["id"]
        return None

def create_dataset(session: requests.Session, db_id, table_name, schema="public"):
    """Create a dataset from a table"""
    dataset_url = f"{SUPERSET_URL}/api/v1/dataset/"
    
    payload = {
        "database": db_id,
        "schema": schema,
        "table_name": table_name
    }
    
    response = session.post(dataset_url, json=payload)
    if response.status_code in [200, 201]:
        print(f"[OK] Dataset created: {table_name}")
        return response.json()["id"]
    else:
        print(f"  Dataset {table_name} may already exist: {response.status_code}")
        return None

def main():
    print("=" * 50)
    print("Superset Configuration Script")
    print("=" * 50)
    
    # Wait for Superset to be ready
    print("\nWaiting for Superset to be ready...")
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(f"{SUPERSET_URL}/health")
            if response.status_code == 200:
                print("[OK] Superset is ready")
                break
        except:
            pass
        time.sleep(2)
        print(f"  Retry {i+1}/{max_retries}...")
    
    # Get access token
    print("\nAuthenticating...")
    session = requests.Session()
    token = get_access_token(session)
    if not token:
        print("Failed to authenticate. Make sure Superset is running.")
        return
    print("[OK] Authenticated")

    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Referer": SUPERSET_URL
    })

    # Get CSRF token
    csrf_token = get_csrf_token(session)
    if csrf_token:
        session.headers["X-CSRFToken"] = csrf_token
    
    # Create database connection
    print("\nCreating database connection...")
    db_id = create_database_connection(session)
    if not db_id:
        print("Failed to create database connection")
        return
    
    # Create datasets for key tables
    print("\nCreating datasets...")
    tables = [
        "mart_daily_kpis",
        "mart_rfm",
        "mart_country_performance",
        "mart_product_performance",
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
    
    for table in tables:
        create_dataset(session, db_id, table)
    
    print("\n" + "=" * 50)
    print("Setup Complete!")
    print("=" * 50)
    print(f"\nAccess Superset at: {SUPERSET_URL}")
    print(f"Username: {USERNAME}")
    print(f"Password: {PASSWORD}")
    print("\nNext steps:")
    print("1. Log into Superset")
    print("2. Go to SQL Lab to explore data")
    print("3. Create charts using the queries in superset/dashboards/dashboard_queries.sql")
    print("4. Combine charts into dashboards")

if __name__ == "__main__":
    main()
