#!/usr/bin/env python3
"""
Direct CSV Ingestion Script
Alternative to n8n Workflow A - directly loads CSV into PostgreSQL
Run this if you prefer Python over n8n for initial data load
"""

import pandas as pd
from sqlalchemy import create_engine, text
import sys
import os

# Configuration
DATABASE_URL = "postgresql://postgres:postgres123@localhost:5432/ecommerce_dw"
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data.csv")
BATCH_SIZE = 10000

def main():
    print("=" * 50)
    print("E-Commerce Data Ingestion Script")
    print("=" * 50)
    
    # Check if CSV exists
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV file not found at {CSV_PATH}")
        sys.exit(1)
    
    print(f"\nReading CSV from: {CSV_PATH}")
    
    # Read CSV
    df = pd.read_csv(CSV_PATH, encoding='latin1')
    print(f"Loaded {len(df):,} records")
    
    # Rename columns to match database schema
    df.columns = [
        'invoice_no', 'stock_code', 'description', 'quantity',
        'invoice_date', 'unit_price', 'customer_id', 'country'
    ]
    
    # Parse dates
    print("Parsing dates...")
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], format='%m/%d/%Y %H:%M', errors='coerce')
    
    # Connect to database
    print(f"\nConnecting to database...")
    engine = create_engine(DATABASE_URL)
    
    # Test connection
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"ERROR: Cannot connect to database: {e}")
        print("\nMake sure Docker containers are running:")
        print("  docker-compose up -d")
        sys.exit(1)
    
    # Clear existing data
    print("\nClearing existing raw data...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE raw_transactions"))
        conn.commit()
    
    # Insert data in batches
    print(f"\nInserting data in batches of {BATCH_SIZE:,}...")
    total_inserted = 0
    
    for i in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[i:i+BATCH_SIZE]
        batch.to_sql('raw_transactions', engine, if_exists='append', index=False)
        total_inserted += len(batch)
        progress = (total_inserted / len(df)) * 100
        print(f"  Progress: {total_inserted:,} / {len(df):,} ({progress:.1f}%)")
    
    print(f"\n✓ Successfully inserted {total_inserted:,} records")
    
    # Verify
    print("\nVerifying insertion...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM raw_transactions")).fetchone()
        print(f"✓ Database contains {result[0]:,} records")
    
    print("\n" + "=" * 50)
    print("Ingestion Complete!")
    print("=" * 50)
    print("\nNext step: Run ETL transforms")
    print("  Option 1: Run Workflow B in n8n")
    print("  Option 2: Execute: SELECT * FROM run_full_etl();")

if __name__ == "__main__":
    main()
