from __future__ import annotations

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from services.stock_lookup import lookup_stock, normalize_symbol


FINNHUB_API_KEY = "d67htm9r01qobepi2mogd67htm9r01qobepi2mp0"


def _with_default_exchange(symbol: str) -> str:
    symbol = str(symbol or "").strip().upper()
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    return f"{symbol}.NS"


def get_market_status() -> dict:
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    is_weekday = now.weekday() < 5
    market_open = dt_time(9, 15) <= now.time() <= dt_time(15, 30)
    is_open = is_weekday and market_open
    return {
        "is_open": is_open,
        "label": "Market Open" if is_open else "Market Closed",
        "color": "#18a874" if is_open else "#e56363",
        "updated_at": now.strftime("%d %b %Y, %I:%M %p IST"),
    }


def get_tradingview_symbol(symbol: str) -> str:
    full_symbol = _with_default_exchange(symbol)
    base, exchange = normalize_symbol(full_symbol)
    prefix = "NSE" if exchange == "NS" else "BSE"
    return f"{prefix}:{base}"


def get_live_quote(symbol: str) -> dict | None:
    full_symbol = _with_default_exchange(symbol)
    try:
        quote = lookup_stock(full_symbol, max_age_seconds=10)
    except Exception:
        return None

    previous_close = quote.get("previous_close") or 0
    price = quote.get("price") or 0
    change = round(price - previous_close, 2) if previous_close else 0
    change_percent = round((change / previous_close) * 100, 2) if previous_close else 0

    return {
        "symbol": quote["base_symbol"],
        "exchange_symbol": quote["symbol"],
        "tradingview_symbol": get_tradingview_symbol(full_symbol),
        "price": price,
        "previous_close": previous_close or None,
        "change": change,
        "change_percent": change_percent,
        "day_high": quote.get("day_high"),
        "day_low": quote.get("day_low"),
        "volume": quote.get("volume"),
        "updated_at": quote.get("updated_at"),
        "market": get_market_status(),
        "provider": "Finnhub/yfinance compatible cache",
    }
