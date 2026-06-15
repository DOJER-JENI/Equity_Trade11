from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

from config import Config


BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DB = BASE_DIR / "screener.db"
SYMBOL_RE = re.compile(r"^[A-Z0-9&-]{1,20}\.(NS|BO)$")


def normalize_symbol(raw_symbol: str) -> tuple[str, str]:
    symbol = str(raw_symbol or "").strip().upper()
    if not SYMBOL_RE.match(symbol):
        raise ValueError("Only NSE/BSE symbols ending with .NS or .BO are allowed.")
    base, exchange = symbol.rsplit(".", 1)
    return base, exchange


def _conn():
    conn = sqlite3.connect(CACHE_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stock_cache (
            symbol TEXT PRIMARY KEY,
            base_symbol TEXT NOT NULL,
            exchange TEXT NOT NULL,
            name TEXT,
            price REAL,
            previous_close REAL,
            day_high REAL,
            day_low REAL,
            volume INTEGER,
            fetched_at INTEGER NOT NULL
        )
        """
    )
    return conn


def get_cached_stock(symbol: str, max_age_seconds: int = 300) -> dict | None:
    base, exchange = normalize_symbol(symbol)
    full_symbol = f"{base}.{exchange}"
    conn = _conn()
    row = conn.execute("SELECT * FROM stock_cache WHERE symbol = ?", (full_symbol,)).fetchone()
    conn.close()

    if not row:
        return None

    data = dict(row)
    data["is_fresh"] = int(time.time()) - int(data["fetched_at"]) <= max_age_seconds
    return data


def fetch_and_store_stock(symbol: str) -> dict:
    base, exchange = normalize_symbol(symbol)
    full_symbol = f"{base}.{exchange}"
    ticker = yf.Ticker(full_symbol)
    fast = ticker.fast_info or {}

    price = fast.get("lastPrice")
    previous_close = fast.get("previousClose")
    day_high = fast.get("dayHigh")
    day_low = fast.get("dayLow")
    volume = fast.get("lastVolume")
    name = base

    try:
        info = ticker.get_info() or {}
        name = info.get("shortName") or info.get("longName") or base
    except Exception:
        pass

    if price is None:
        hist = ticker.history(period="5d", interval="1d")
        if hist.empty:
            raise ValueError("Stock was not found from the market data provider.")
        latest = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) > 1 else latest
        price = float(latest["Close"])
        previous_close = float(previous["Close"])
        day_high = float(latest["High"])
        day_low = float(latest["Low"])
        volume = int(latest["Volume"])

    data = {
        "symbol": full_symbol,
        "base_symbol": base,
        "exchange": exchange,
        "name": name,
        "price": round(float(price), 2),
        "previous_close": round(float(previous_close), 2) if previous_close else None,
        "day_high": round(float(day_high), 2) if day_high else None,
        "day_low": round(float(day_low), 2) if day_low else None,
        "volume": int(volume) if volume else None,
        "fetched_at": int(time.time()),
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }

    conn = _conn()
    conn.execute(
        """
        INSERT INTO stock_cache (
            symbol, base_symbol, exchange, name, price, previous_close,
            day_high, day_low, volume, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            name = excluded.name,
            price = excluded.price,
            previous_close = excluded.previous_close,
            day_high = excluded.day_high,
            day_low = excluded.day_low,
            volume = excluded.volume,
            fetched_at = excluded.fetched_at
        """,
        (
            data["symbol"],
            data["base_symbol"],
            data["exchange"],
            data["name"],
            data["price"],
            data["previous_close"],
            data["day_high"],
            data["day_low"],
            data["volume"],
            data["fetched_at"],
        ),
    )
    conn.commit()
    conn.close()
    return data


def lookup_stock(symbol: str, max_age_seconds: int = 300) -> dict:
    cached = get_cached_stock(symbol, max_age_seconds=max_age_seconds)
    if cached and cached.get("is_fresh"):
        return cached
    return fetch_and_store_stock(symbol)


def to_app_company(symbol: str) -> str:
    base, _exchange = normalize_symbol(symbol)
    return base
