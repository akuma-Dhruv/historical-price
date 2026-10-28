from __future__ import annotations

import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

import pyotp
from SmartApi import SmartConnect

INTERVALS = {
    "1m": ("ONE_MINUTE", 30),
    "3m": ("THREE_MINUTE", 60),
    "5m": ("FIVE_MINUTE", 100),
    "10m": ("TEN_MINUTE", 100),
    "15m": ("FIFTEEN_MINUTE", 200),
    "30m": ("THIRTY_MINUTE", 200),
    "1h": ("ONE_HOUR", 400),
    "1d": ("ONE_DAY", 2000),
}


def validate_range(interval: str, start: datetime, end: datetime) -> None:
    if interval not in INTERVALS:
        raise ValueError(f"Unsupported interval {interval!r}; choose from {', '.join(INTERVALS)}")
    if end <= start:
        raise ValueError("end must be after start")
    if end - start > timedelta(days=INTERVALS[interval][1]):
        raise ValueError(
            f"{interval} supports at most {INTERVALS[interval][1]} days per request/lookback "
            "according to Angel One SmartAPI limits"
        )


class AngelOneClient:
    def __init__(self, api_key: str, client_code: str, pin: str, totp_secret: str, request_spacing: float = 1.2):
        self.api = SmartConnect(api_key=api_key)
        response = self.api.generateSession(client_code, pin, pyotp.TOTP(totp_secret).now())
        if not response.get("status"):
            raise RuntimeError(f"Angel One login failed: {response.get('message', 'unknown error')}")
        self._last_request = 0.0
        self._spacing = request_spacing
        self._lock = Lock()

    def candles(self, exchange: str, token: str, interval: str, start: datetime, end: datetime) -> list[list[Any]]:
        validate_range(interval, start, end)
        api_interval, _ = INTERVALS[interval]
        with self._lock:
            delay = self._spacing - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            response = self.api.getCandleData({
                "exchange": exchange,
                "symboltoken": token,
                "interval": api_interval,
                "fromdate": start.strftime("%Y-%m-%d %H:%M"),
                "todate": end.strftime("%Y-%m-%d %H:%M"),
            })
            self._last_request = time.monotonic()
        if not response.get("status"):
            raise RuntimeError(response.get("message", "Angel One returned no candle data"))
        return response.get("data") or []

