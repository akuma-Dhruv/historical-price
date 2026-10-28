from __future__ import annotations

from typing import Iterable

import psycopg

SCHEMA = """
CREATE TABLE IF NOT EXISTS historical_prices (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    symbol_token TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    candle_time TIMESTAMPTZ NOT NULL,
    open NUMERIC NOT NULL CHECK (open >= 0),
    high NUMERIC NOT NULL CHECK (high >= 0),
    low NUMERIC NOT NULL CHECK (low >= 0),
    close NUMERIC NOT NULL CHECK (close >= 0),
    volume NUMERIC NOT NULL CHECK (volume >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT historical_prices_unique_candle
      UNIQUE (exchange, symbol_token, timeframe, candle_time),
    CONSTRAINT historical_prices_ohlc_order
      CHECK (high >= low AND high >= open AND high >= close AND low <= open AND low <= close)
);
CREATE INDEX IF NOT EXISTS historical_prices_symbol_time_idx
  ON historical_prices (symbol, timeframe, candle_time DESC);
CREATE INDEX IF NOT EXISTS historical_prices_token_time_idx
  ON historical_prices (symbol_token, timeframe, candle_time DESC);
CREATE TABLE IF NOT EXISTS download_progress (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    symbol_token TEXT NOT NULL,
    exchange TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    candles_inserted INTEGER NOT NULL DEFAULT 0 CHECK (candles_inserted >= 0),
    last_error TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT download_progress_unique_job
      UNIQUE (exchange, symbol_token, timeframe, start_time, end_time)
);
"""


def initialize(database_url: str) -> None:
    with psycopg.connect(database_url) as connection:
        connection.execute(SCHEMA)


def insert_candles(database_url: str, exchange: str, token: str, symbol: str, interval: str,
                   candles: Iterable[list]) -> int:
    rows = []
    for candle in candles:
        if len(candle) < 6:
            raise ValueError(f"Unexpected candle shape: {candle!r}")
        rows.append((symbol, token, exchange, interval, *candle[:6]))
    if not rows:
        return 0
    sql = """
    INSERT INTO historical_prices
      (symbol, symbol_token, exchange, timeframe, candle_time, open, high, low, close, volume)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (exchange, symbol_token, timeframe, candle_time) DO UPDATE SET
      symbol = EXCLUDED.symbol, open = EXCLUDED.open, high = EXCLUDED.high,
      low = EXCLUDED.low, close = EXCLUDED.close, volume = EXCLUDED.volume
    """
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(sql, rows)
    return len(rows)


def set_progress(database_url: str, symbol: str, token: str, exchange: str, timeframe: str,
                 start, end, status: str, attempts: int, candles_inserted: int = 0,
                 last_error: str | None = None) -> None:
    sql = """
    INSERT INTO download_progress
      (symbol, symbol_token, exchange, timeframe, start_time, end_time, status,
       attempts, candles_inserted, last_error)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (exchange, symbol_token, timeframe, start_time, end_time) DO UPDATE SET
      status = EXCLUDED.status, attempts = EXCLUDED.attempts,
      candles_inserted = EXCLUDED.candles_inserted, last_error = EXCLUDED.last_error,
      updated_at = NOW()
    """
    with psycopg.connect(database_url) as connection:
        connection.execute(sql, (symbol, token, exchange, timeframe, start, end, status,
                                  attempts, candles_inserted, last_error))


def list_progress(database_url: str, status: str | None = None) -> list[tuple]:
    query = "SELECT symbol, symbol_token, exchange, timeframe, start_time, end_time, status, attempts, candles_inserted, last_error FROM download_progress"
    params: tuple[str, ...] = ()
    if status:
        query += " WHERE status = %s"
        params = (status,)
    query += " ORDER BY updated_at DESC"
    with psycopg.connect(database_url) as connection:
        return connection.execute(query, params).fetchall()
