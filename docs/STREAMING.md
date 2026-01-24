# Streaming / Micro-Batch Ingestion

This project includes an optional micro-batch streamer that simulates near real-time ingestion from `data.csv`.
It inserts rows in batches, triggers ETL refresh, and can optionally trigger ML training.
Each batch runs the full ETL function (`run_full_etl()`), which is fine for demo data but can be heavy at scale.

## Start the streamer

```bash
docker-compose --profile streaming up -d streamer
```

## Stop the streamer

```bash
docker-compose --profile streaming stop streamer
```

## Run a one-off ETL cycle

```bash
docker-compose --profile streaming run --rm streamer python etl_runner.py
```

## Configuration

These environment variables are defined in `docker-compose.yml` for the streamer service:

- `BATCH_SIZE` (default 1000)
- `SLEEP_SECONDS` (default 30)
- `RUN_ETL` (default true)
- `RUN_ML` (default false)
- `CSV_PATH` (default `/data/data.csv`)
- `STATE_PATH` (default `/data/stream_state.json`)

## Reset the stream position

Delete the state file and restart the streamer:

```bash
# PowerShell
Remove-Item data\\stream_state.json

# Bash
rm data/stream_state.json
```
