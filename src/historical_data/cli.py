from __future__ import annotations

from datetime import datetime

import typer

from .angel import AngelOneClient, INTERVALS, validate_range
from .config import load_settings
from .db import initialize, insert_candles, list_progress, set_progress

app = typer.Typer(no_args_is_help=True)


@app.command()
def limits() -> None:
    """Print Angel One's enforced maximum historical lookback windows."""
    for interval, (_, days) in INTERVALS.items():
        typer.echo(f"{interval}: {days} days")


@app.command()
def init_db(database_url: str | None = typer.Option(None, envvar="DATABASE_URL"),
            env_file: str | None = typer.Option(None, help="Explicit environment file path")) -> None:
    """Create required PostgreSQL tables and indexes without deleting data."""
    settings = load_settings(env_file) if not database_url else None
    database_url = database_url or (settings.database_url if settings else None)
    if not database_url:
        raise typer.BadParameter("Pass --database-url or set DATABASE_URL in the selected environment file.")
    initialize(database_url)
    typer.echo("Database schema is ready.")


@app.command()
def download(
    exchange: str = typer.Option("NSE"),
    token: str = typer.Option(..., help="Angel One symbol token"),
    symbol: str = typer.Option(..., help="Human-readable symbol"),
    interval: str = typer.Option("1d"),
    start: datetime = typer.Option(..., formats=["%Y-%m-%dT%H:%M"]),
    end: datetime = typer.Option(..., formats=["%Y-%m-%dT%H:%M"]),
    env_file: str | None = typer.Option(None, help="Explicit path to the parent .env"),
    database_url: str | None = typer.Option(None, envvar="DATABASE_URL"),
    dry_run: bool = typer.Option(False, help="Validate settings and range without API or database writes"),
) -> None:
    """Download a supported range and upsert candles into PostgreSQL."""
    settings = load_settings(env_file)
    database = database_url or settings.database_url
    if not database:
        raise typer.BadParameter("Pass --database-url or set DATABASE_URL; it is not read from the parent API credentials.")
    validate_range(interval, start, end)
    if dry_run:
        typer.echo(f"Dry run valid: {symbol} {exchange} {token} {interval} {start.isoformat()} to {end.isoformat()}")
        return
    initialize(database)
    client = AngelOneClient(settings.api_key, settings.client_code, settings.pin, settings.totp_secret)
    rows = list_progress(database, "completed")
    existing = next((row for row in rows if row[1] == token and row[2] == exchange and row[3] == interval
                     and row[4] == start and row[5] == end), None)
    if existing:
        typer.echo("Download already completed; no request made.")
        return
    attempts = 1
    set_progress(database, symbol, token, exchange, interval, start, end, "running", attempts)
    try:
        candles = client.candles(exchange, token, interval, start, end)
        count = insert_candles(database, exchange, token, symbol, interval, candles)
        set_progress(database, symbol, token, exchange, interval, start, end, "completed", attempts, count)
    except Exception as error:
        set_progress(database, symbol, token, exchange, interval, start, end, "failed", attempts, 0, str(error))
        raise
    typer.echo(f"Upserted {count} candles for {symbol} ({interval}).")


@app.command()
def progress(database_url: str | None = typer.Option(None, envvar="DATABASE_URL"),
             env_file: str | None = typer.Option(None, help="Explicit environment file path"),
             status: str | None = typer.Option(None, help="Filter: running, completed, or failed")) -> None:
    """List tracked download jobs without exposing credentials."""
    settings = load_settings(env_file)
    database_url = database_url or settings.database_url
    if not database_url:
        raise typer.BadParameter("Pass --database-url or set DATABASE_URL in the selected environment file.")
    for row in list_progress(database_url, status):
        typer.echo(" | ".join(str(value) for value in row))


if __name__ == "__main__":
    app()
