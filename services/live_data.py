import time

import yfinance as yf


price_cache = {}
cache_time = {}


def get_live_price(symbol):
    symbol = symbol.upper().strip()
    now = time.time()
    if symbol in price_cache and (now - cache_time.get(symbol, 0)) < 8:
        return price_cache[symbol]

    try:
        ticker = yf.Ticker(symbol + ".NS")
        fast = ticker.fast_info
        price = fast.get("lastPrice")
        if price is None:
            hist = ticker.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        if price is not None:
            price_cache[symbol] = round(float(price), 2)
            cache_time[symbol] = now
            return price_cache[symbol]
    except Exception:
        pass

    return price_cache.get(symbol)


def get_all_live_prices(companies):
    result = {}
    for company in companies:
        price = get_live_price(company)
        if price is not None:
            result[company] = price
    return result


def get_live_price_with_change(symbol):
    symbol = symbol.upper().strip()
    try:
        ticker = yf.Ticker(symbol + ".NS")
        hist = ticker.history(period="5d")
        if len(hist) >= 2:
            current = float(hist["Close"].iloc[-1])
            previous = float(hist["Close"].iloc[-2])
            change = round(current - previous, 2)
            change_pct = round((change / previous) * 100, 2) if previous else 0
            return {
                "price": round(current, 2),
                "change": change,
                "change_percent": change_pct,
                "previous_close": round(previous, 2),
            }
    except Exception:
        pass

    price = get_live_price(symbol)
    if price is not None:
        return {
            "price": price,
            "change": 0,
            "change_percent": 0,
            "previous_close": price,
        }
    return None