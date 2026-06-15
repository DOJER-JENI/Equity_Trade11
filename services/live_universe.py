from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from config import Config
from indicators import calculate_indicators


DATA_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume", "Company"]


def normalize_company(symbol: str) -> str:
    return str(symbol or "").strip().upper().split(".")[0]


def _history_from_yfinance(symbol: str) -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="9mo", interval="1d", auto_adjust=False, timeout=5)
    if hist.empty:
        return pd.DataFrame(columns=DATA_COLUMNS)

    hist = hist.reset_index()
    hist["Company"] = normalize_company(symbol)
    hist = hist.rename(columns={"Date": "Date"})
    return hist[["Date", "Open", "High", "Low", "Close", "Volume", "Company"]]


def _fallback_history(symbol: str, days: int = 140) -> pd.DataFrame:
    company = normalize_company(symbol)
    seed = sum(ord(ch) for ch in company)
    rng = random.Random(seed)
    base = 250 + (seed % 2400)
    rows = []
    today = datetime.utcnow().date()

    for i in range(days):
        date = today - timedelta(days=days - i)
        drift = math.sin(i / 8) * 0.018 + rng.uniform(-0.012, 0.012)
        close = max(10, base * (1 + drift + (i / days) * rng.uniform(-0.04, 0.08)))
        open_price = close * (1 + rng.uniform(-0.01, 0.01))
        high = max(open_price, close) * (1 + rng.uniform(0.002, 0.018))
        low = min(open_price, close) * (1 - rng.uniform(0.002, 0.018))
        rows.append(
            {
                "Date": pd.Timestamp(date),
                "Open": round(open_price, 2),
                "High": round(high, 2),
                "Low": round(low, 2),
                "Close": round(close, 2),
                "Volume": int(150000 + rng.random() * 5000000),
                "Company": company,
            }
        )

    return pd.DataFrame(rows, columns=DATA_COLUMNS)


def _fundamentals(symbol: str, company: str) -> dict:
    fallback = {
        "PE": 12 + (sum(ord(c) for c in company) % 38),
        "EPS": 8 + (sum(ord(c) for c in company) % 90),
        "MarketCap": 5000 + (sum(ord(c) for c in company) * 120),
        "BookValue": 40 + (sum(ord(c) for c in company) % 260),
        "ROE": round(0.08 + (sum(ord(c) for c in company) % 25) / 100, 3),
        "ROA": round(0.03 + (sum(ord(c) for c in company) % 12) / 100, 3),
    }

    if not Config.USE_LIVE_BOOTSTRAP:
        return fallback

    try:
        fast = yf.Ticker(symbol).fast_info or {}
        info = {}
        fallback.update(
            {
                "MarketCap": fast.get("marketCap") or fallback["MarketCap"],
            }
        )
    except Exception:
        pass

    return fallback


def build_live_universe(symbols: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for symbol in symbols or Config.DEFAULT_SYMBOLS:
        frame = pd.DataFrame(columns=DATA_COLUMNS)
        if Config.USE_LIVE_BOOTSTRAP:
            try:
                frame = _history_from_yfinance(symbol)
            except Exception:
                frame = pd.DataFrame(columns=DATA_COLUMNS)
        if frame.empty:
            frame = _fallback_history(symbol)
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DATA_COLUMNS)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"])

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["Company"] = df["Company"].map(normalize_company)
    df = calculate_indicators(df)

    for col in ["PE", "EPS", "MarketCap", "BookValue", "ROE", "ROA"]:
        df[col] = None

    for symbol in symbols or Config.DEFAULT_SYMBOLS:
        company = normalize_company(symbol)
        funda = _fundamentals(symbol, company)
        for key, value in funda.items():
            df.loc[df["Company"] == company, key] = value

    return df
