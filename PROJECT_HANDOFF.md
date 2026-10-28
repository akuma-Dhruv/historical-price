# Project Handoff

## Project objective

`historical-market-data` is a separate repository for downloading bounded Angel
One historical candles and storing OHLCV data in PostgreSQL for later
backtesting. It is not the live-price application and does not run its FastAPI
dashboard or WebSocket.

## Repository boundary

The repository is separate from `/home/martin/Documents/live-price`. The
downloader reuses only the parent environment variables and the same
`SmartConnect.generateSession` plus TOTP flow; it never imports or starts
`main.py`. The original machine's parent environment path is
`/home/martin/Documents/live-price/.env`, but other developers must pass their
own absolute `--env-file` or create a local `.env`.

## Current architecture

CLI configuration -> Angel One authentication -> bounded historical candle
request -> PostgreSQL validation/upsert -> download progress update. There is
no instrument-master downloader, multi-symbol scheduler, or backtesting engine
yet.

## File and module map

- `src/historical_data/config.py`: local/explicit environment selection and
  environment-variable precedence.
- `src/historical_data/angel.py`: SmartAPI authentication, interval limits,
  request pacing, and candle retrieval.
- `src/historical_data/db.py`: idempotent schema creation, OHLCV upserts, and
  progress persistence.
- `src/historical_data/cli.py`: `limits`, `init-db`, `download`, and `progress`.
- `tests/test_angel.py`: interval and range validation tests.
- `Dockerfile`, `.dockerignore`, `compose.yaml`: optional reproducible runtime
  and PostgreSQL service.

## Database contract

`historical_prices` contains `id`, `symbol`, `symbol_token`, `exchange`,
`timeframe`, `candle_time`, `open`, `high`, `low`, `close`, `volume`, and
`created_at`. OHLC values are non-negative and satisfy high/low ordering;
volume is non-negative. The unique constraint is
`(exchange, symbol_token, timeframe, candle_time)`. Indexes support
symbol/timeframe/time and token/timeframe/time queries.

`download_progress` tracks one bounded job by symbol, token, exchange,
timeframe, start/end, status, attempts, inserted count, error, and update time.
Timestamps are PostgreSQL `timestamptz`; SmartAPI timestamps are passed through
the PostgreSQL driver.

## Authentication and configuration

Required names are `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`,
`ANGEL_TOTP_SECRET`, and `DATABASE_URL` for database operations. Selection
precedence is explicit `--env-file`, then `HISTORICAL_ENV_FILE`, then local
`.env`, then the original parent path fallback. Process environment values
override file values, and explicit `--database-url` overrides both. Secrets are
never printed.

## Verified commands

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/python -m historical_data.cli limits
.venv/bin/python -m historical_data.cli init-db
.venv/bin/python -m historical_data.cli download --dry-run \
  --token 3045 --symbol SBIN-EQ --interval 1d \
  --start 2025-01-01T09:15 --end 2025-02-01T15:30
.venv/bin/python -m historical_data.cli progress
.venv/bin/python -m pytest -q
docker build -t historical-market-data:local .
docker compose up -d postgres
```

## Data ingestion behavior

Angel One limits are enforced before requests: 1m 30 days, 3m 60, 5m/10m
100, 15m/30m 200, 1h 400, and 1d 2,000. Requests are paced at 1.2 seconds.
Each bounded command records running/completed/failed status and inserts candles
in one PostgreSQL transaction. Upserts prevent duplicate candles. Re-running a
completed identical job skips the API request; failed jobs can be retried by
rerunning the command. No automatic multi-range orchestration exists yet.

## Current limitations and next steps

Angel One's limits do not satisfy a full 10-year history. A licensed provider
or imported dataset is needed for missing years; no replacement provider is
integrated. Next priorities:

1. Complete a small real download and verify stored candles.
2. Verify interruption and retry behavior.
3. Verify duplicate prevention against PostgreSQL.
4. Evaluate additional sources for 10-year coverage.
5. Expand symbols/timeframes after performance and storage validation.
6. Build the backtesting engine in a separate task.

## Validation results

The repository has unit tests for interval/range validation and compile checks.
Configuration loading was verified against the parent path without printing
credentials. PostgreSQL integration, real broker download, and Docker build
require local services/credentials and must be run by the next developer.

## Handoff safety

Read this file first, inspect source and Git status, check configuration without
printing secrets, run tests, and make incremental changes. Do not modify the
parent project unless explicitly requested. Do not commit `.env`, database
dumps, or credentials.
