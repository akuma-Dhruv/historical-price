# Historical Market Data

Independent Angel One SmartAPI ingestion for preparing OHLCV data for future
backtesting. This repository does not import, start, or modify the
`live-price` dashboard and does not open its WebSocket.

## Prerequisites

- Python 3.10 or newer
- PostgreSQL 14 or newer (or a compatible PostgreSQL service)
- An Angel One SmartAPI application and trading-account credentials
- Docker and Docker Compose, optional

The project uses `psycopg` with PostgreSQL connection URLs such as
`postgresql://user:password@host:5432/database`.

## Install

```bash
git clone <repository-url> historical-market-data
cd historical-market-data
python3 -m venv .venv
# Linux/macOS:
. .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
python -m pip install -e '.[test]'
```

## Configuration and secrets

For a standalone checkout, create a local environment file:

```bash
cp -n .env.example .env
chmod 600 .env
```

If `.env` already exists, inspect and edit it deliberately; `cp -n` will not
overwrite it.

Fill in the four `ANGEL_*` variables and a PostgreSQL `DATABASE_URL` securely.
`.env` and all `.env.*` files except `.env.example` are ignored by Git.
Existing process environment variables override values from the selected file;
an explicit CLI option such as `--database-url` overrides both.

The original parent project can be used without copying its credentials:

```bash
.venv/bin/python -m historical_data.cli limits \
  # commands that need credentials:
.venv/bin/python -m historical_data.cli download \
  --env-file /absolute/path/to/live-price/.env \
  --database-url postgresql://user:password@localhost:5432/historical_market_data \
  --token 3045 --symbol SBIN-EQ --interval 1d \
  --start 2025-01-01T09:15 --end 2025-02-01T15:30
```

`--env-file` takes precedence over `HISTORICAL_ENV_FILE`; otherwise the
repository-local `.env` is preferred, with the historical parent path used only
as a compatibility fallback on the original machine. No secret is printed.

## PostgreSQL initialization

### Local PostgreSQL

Create a database and user as an administrator, then put the resulting URL in
`.env`:

```sql
CREATE USER historical_user WITH PASSWORD 'use-a-local-secret';
CREATE DATABASE historical_market_data OWNER historical_user;
```

Initialize the schema:

```bash
.venv/bin/python -m historical_data.cli init-db
```

Or explicitly:

```bash
.venv/bin/python -m historical_data.cli init-db \
  --database-url postgresql://historical_user:password@localhost:5432/historical_market_data
```

Initialization is idempotent and never drops historical rows. It creates
`historical_prices`, its unique constraint and indexes, and `download_progress`.
Verify with:

```sql
\dt
\d historical_prices
\d download_progress
\di historical_prices*
```

### Docker PostgreSQL

Create `.env` with at least `POSTGRES_PASSWORD`, `DATABASE_URL`, and optionally
`POSTGRES_DB`, `POSTGRES_USER`, or `POSTGRES_PORT`. The application connects to
the Compose service name, not `localhost`:

```env
POSTGRES_DB=historical_market_data
POSTGRES_USER=historical_user
POSTGRES_PASSWORD=use_a-local-secret
DATABASE_URL=postgresql://historical_user:use_a-local-secret@postgres:5432/historical_market_data
```

Start PostgreSQL with persistent named storage and wait for health:

```bash
docker compose up -d postgres
docker compose ps
docker run --rm --network historical-market-data_default \
  --env-file .env historical-market-data:local init-db
```

The default host port is `5432`; change `POSTGRES_PORT` if occupied. Data is
stored in the `historical-postgres-data` named volume. When the downloader runs
directly on the host, use `localhost`; from a Compose network, use `postgres`.

## Test and dry run

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q src tests
```

A dry run validates the selected environment, symbol, timeframe, and date range
without authenticating, calling Angel One, or writing to PostgreSQL:

```bash
.venv/bin/python -m historical_data.cli download --dry-run \
  --token 3045 --symbol SBIN-EQ --interval 1d \
  --start 2025-01-01T09:15 --end 2025-02-01T15:30
```

## Download, progress, resume, and retry

Initialize once, then download a small range:

```bash
.venv/bin/python -m historical_data.cli init-db
.venv/bin/python -m historical_data.cli download \
  --token 3045 --symbol SBIN-EQ --interval 1d \
  --start 2025-01-01T09:15 --end 2025-02-01T15:30
```

Inspect jobs:

```bash
.venv/bin/python -m historical_data.cli progress
.venv/bin/python -m historical_data.cli progress --status failed
```

An interrupted or failed job is recorded in `download_progress`. Re-run the same
download command to retry it; completed identical jobs are skipped. Candle
upserts use `(exchange, symbol_token, timeframe, candle_time)`, so retries do
not create duplicates. The current CLI downloads one bounded range per command;
larger histories should be split into ranges that obey the limits.

## Historical API limits

The implementation enforces these maximum lookbacks:

| Timeframe | Maximum lookback |
|---|---:|
| 1m | 30 days |
| 3m | 60 days |
| 5m | 100 days |
| 10m | 100 days |
| 15m | 200 days |
| 30m | 200 days |
| 1h | 400 days |
| 1d | 2,000 days |

```bash
.venv/bin/python -m historical_data.cli limits
```

These are enforced request/lookback limits, not a completed 10-year dataset.
Angel One alone cannot currently provide a full 10 years for these intervals;
daily data reaches only about 5.5 years at best. An alternative licensed source
or separately imported dataset is required for older years, and none is
integrated here.

## Useful SQL

```sql
SELECT symbol, timeframe, count(*)
FROM historical_prices GROUP BY symbol, timeframe ORDER BY symbol, timeframe;

SELECT * FROM historical_prices
WHERE symbol = 'SBIN-EQ' ORDER BY candle_time DESC LIMIT 20;

SELECT * FROM historical_prices
WHERE symbol = 'SBIN-EQ' AND timeframe = '1d'
  AND candle_time >= '2025-01-01' AND candle_time < '2025-02-01'
ORDER BY candle_time;

SELECT candle_time, candle_time - lag(candle_time) OVER (ORDER BY candle_time) AS gap
FROM historical_prices WHERE symbol = 'SBIN-EQ' AND timeframe = '1d'
ORDER BY candle_time;

SELECT exchange, symbol_token, timeframe, candle_time, count(*)
FROM historical_prices
GROUP BY exchange, symbol_token, timeframe, candle_time HAVING count(*) > 1;

SELECT * FROM download_progress ORDER BY updated_at DESC;
```

## Troubleshooting

- **Missing variables:** use `--env-file` or create `.env`; do not paste secrets
  into commands or documentation.
- **Invalid credentials/session:** verify the four Angel variables and TOTP
  clock synchronization; the client reports the broker error without secrets.
- **PostgreSQL connection failure:** check the URL, server status, port, user,
  database, and Docker hostname (`postgres` inside Compose).
- **Missing tables:** run `init-db` against the same database URL used by
  `download`.
- **Rate limits:** requests are paced at 1.2 seconds; retry later rather than
  starting multiple downloaders.
- **Unavailable period:** shorten the range to the table above and confirm the
  instrument token/exchange.
- **Interrupted download:** inspect `progress`, then rerun the same command.
- **Duplicate candles:** the unique constraint and upsert prevent duplicates.
- **Disk space:** inspect PostgreSQL volume usage before large imports.

## Docker downloader

Build without copying secrets:

```bash
docker build -t historical-market-data:local .
docker run --rm --env-file .env historical-market-data:local limits
docker run --rm --env-file .env historical-market-data:local download --dry-run \
  --token 3045 --symbol SBIN-EQ --interval 1d \
  --start 2025-01-01T09:15 --end 2025-02-01T15:30
```

The image has a non-root user and an overridable CLI entrypoint. It never starts
the live dashboard or a large download automatically. A failed CLI command
returns a non-zero container exit status.
