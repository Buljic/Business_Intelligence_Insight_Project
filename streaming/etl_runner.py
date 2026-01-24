import os

from streamer import connect_db, run_etl_cycle


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required")

    run_ml = os.getenv("RUN_ML", "false").lower() == "true"
    ml_service_url = os.getenv("ML_SERVICE_URL", "http://ml_service:8000")
    source_file = os.getenv("SOURCE_FILE", "manual")
    refresh_type = os.getenv("REFRESH_TYPE", "full")

    conn = connect_db(database_url)
    conn.autocommit = False
    run_etl_cycle(conn, source_file, refresh_type, run_ml, ml_service_url)
    conn.close()


if __name__ == "__main__":
    main()