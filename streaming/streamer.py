import argparse
import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_values
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("streamer")


def load_state(state_path: str) -> Dict:
    if not os.path.exists(state_path):
        return {"line_number": 0}
    with open(state_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(state_path: str, line_number: int) -> None:
    state = {
        "line_number": line_number,
        "updated_at": datetime.utcnow().isoformat() + "Z"
    }
    with open(state_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle)


def connect_db(database_url: str):
    return psycopg2.connect(database_url)


def parse_invoice_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def to_int(value: str) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def to_float(value: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def row_to_tuple(row: Dict) -> Tuple:
    return (
        row.get("InvoiceNo"),
        row.get("StockCode"),
        row.get("Description"),
        to_int(row.get("Quantity")),
        parse_invoice_date(row.get("InvoiceDate")),
        to_float(row.get("UnitPrice")),
        row.get("CustomerID"),
        row.get("Country")
    )


def iter_csv_rows(csv_path: str, start_line: int) -> Iterable[Tuple[int, Dict]]:
    with open(csv_path, newline="", encoding="latin-1") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            if index <= start_line:
                continue
            yield index, row


def insert_batch(conn, batch: List[Tuple]) -> None:
    if not batch:
        return
    query = """
        INSERT INTO raw_transactions (
            invoice_no, stock_code, description, quantity,
            invoice_date, unit_price, customer_id, country
        ) VALUES %s
    """
    with conn.cursor() as cur:
        execute_values(cur, query, batch, page_size=1000)
    conn.commit()


def start_etl_run(conn, run_type: str, source_file: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_run_log (run_type, source_file, status)
            VALUES (%s, %s, 'running')
            RETURNING run_id
            """,
            (run_type, source_file)
        )
        run_id = cur.fetchone()[0]
    conn.commit()
    return run_id


def finish_etl_run(conn, run_id: int, status: str, error_message: Optional[str]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl_run_log
            SET status = %s,
                completed_at = CURRENT_TIMESTAMP,
                error_message = %s
            WHERE run_id = %s
            """,
            (status, error_message, run_id)
        )
    conn.commit()


def run_full_etl(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM run_full_etl();")
        cur.fetchall()
    conn.commit()


def run_data_quality_checks(conn, run_id: int) -> List[Tuple[str, bool, str, str]]:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM run_data_quality_checks(%s, TRUE);", (run_id,))
        results = cur.fetchall()
    conn.commit()
    return results


def update_table_refresh_log(conn, table_name: str, run_id: Optional[int],
                             refresh_type: str, duration_ms: Optional[int]) -> None:
    with conn.cursor() as cur:
        count_query = sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(table_name))
        cur.execute(count_query)
        row_count = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO table_refresh_log (
                table_name, last_refresh_at, refresh_run_id,
                row_count, refresh_duration_ms, refresh_type
            ) VALUES (%s, CURRENT_TIMESTAMP, %s, %s, %s, %s)
            ON CONFLICT (table_name) DO UPDATE SET
                last_refresh_at = EXCLUDED.last_refresh_at,
                refresh_run_id = EXCLUDED.refresh_run_id,
                row_count = EXCLUDED.row_count,
                refresh_duration_ms = EXCLUDED.refresh_duration_ms,
                refresh_type = EXCLUDED.refresh_type
            """,
            (table_name, run_id, row_count, duration_ms, refresh_type)
        )
    conn.commit()


def trigger_ml(ml_url: str) -> None:
    try:
        response = requests.post(f"{ml_url.rstrip('/')}/train", timeout=60)
        if response.status_code >= 400:
            logger.warning("ML train request failed: %s", response.text)
        else:
            logger.info("ML train triggered")
    except requests.RequestException as exc:
        logger.warning("ML train request error: %s", exc)


def run_etl_cycle(conn, source_file: str, refresh_type: str, run_ml: bool, ml_url: str) -> None:
    run_id = start_etl_run(conn, "etl_full", source_file)
    status = "success"
    error_message = None
    start_time = time.time()
    try:
        run_full_etl(conn)
        dq_results = run_data_quality_checks(conn, run_id)
        if any((not passed and severity == "critical") for _, passed, severity, _ in dq_results):
            status = "failed"
            error_message = "Critical data quality check failed"
    except Exception as exc:
        conn.rollback()
        status = "failed"
        error_message = str(exc)
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        finish_etl_run(conn, run_id, status, error_message)
        for table_name in [
            "raw_transactions",
            "stg_transactions_clean",
            "fact_sales",
            "mart_daily_kpis",
            "mart_rfm",
            "mart_country_performance",
            "mart_product_performance",
            "ml_forecast_daily",
            "ml_anomalies_daily"
        ]:
            update_table_refresh_log(conn, table_name, run_id, refresh_type, duration_ms)

    if run_ml:
        trigger_ml(ml_url)


def stream_batches(args) -> None:
    state = load_state(args.state_path)
    line_number = int(state.get("line_number", 0))

    conn = connect_db(args.database_url)
    conn.autocommit = False

    logger.info("Starting stream from line %s", line_number)

    while True:
        batch = []
        last_line = line_number
        for index, row in iter_csv_rows(args.csv_path, line_number):
            batch.append(row_to_tuple(row))
            last_line = index
            if len(batch) >= args.batch_size:
                insert_batch(conn, batch)
                update_table_refresh_log(conn, "raw_transactions", None, "incremental", None)
                line_number = last_line
                save_state(args.state_path, line_number)
                if args.run_etl:
                    run_etl_cycle(conn, args.csv_path, "incremental", args.run_ml, args.ml_service_url)
                batch = []
                time.sleep(args.sleep_seconds)

        if batch:
            insert_batch(conn, batch)
            update_table_refresh_log(conn, "raw_transactions", None, "incremental", None)
            line_number = last_line
            save_state(args.state_path, line_number)
            if args.run_etl:
                run_etl_cycle(conn, args.csv_path, "incremental", args.run_ml, args.ml_service_url)

        if not args.loop:
            logger.info("Reached end of file, stopping")
            break

        logger.info("Reached end of file, waiting for new data")
        time.sleep(args.sleep_seconds)

    conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream CSV rows into Postgres.")
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--csv-path", default=os.getenv("CSV_PATH", "/data/data.csv"))
    parser.add_argument("--state-path", default=os.getenv("STATE_PATH", "/data/stream_state.json"))
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("BATCH_SIZE", "1000")))
    parser.add_argument("--sleep-seconds", type=int, default=int(os.getenv("SLEEP_SECONDS", "30")))
    parser.add_argument("--run-etl", action="store_true", default=os.getenv("RUN_ETL", "true").lower() == "true")
    parser.add_argument("--run-ml", action="store_true", default=os.getenv("RUN_ML", "false").lower() == "true")
    parser.add_argument("--ml-service-url", default=os.getenv("ML_SERVICE_URL", "http://ml_service:8000"))
    parser.add_argument("--loop", action="store_true", default=os.getenv("STREAM_LOOP", "false").lower() == "true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit("DATABASE_URL is required")
    stream_batches(args)


if __name__ == "__main__":
    main()
