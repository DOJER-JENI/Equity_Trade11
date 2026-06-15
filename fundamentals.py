import yfinance as yf


fund_cache = {}


def _empty_fundamentals():
    return {
        "PE": None,
        "EPS": None,
        "MarketCap": None,
        "BookValue": None,
        "ROE": None,
        "ROA": None,
        "High52": None,
        "Low52": None,
    }


def get_fundamentals(symbol):
    symbol = symbol.upper().strip()
    if symbol in fund_cache:
        return fund_cache[symbol]

    result = _empty_fundamentals()

    try:
        stock = yf.Ticker(symbol + ".NS")
        info = stock.info or {}
        result.update(
            {
                "PE": info.get("trailingPE"),
                "EPS": info.get("trailingEps"),
                "MarketCap": info.get("marketCap"),
                "BookValue": info.get("bookValue"),
                "ROE": info.get("returnOnEquity"),
                "ROA": info.get("returnOnAssets"),
                "High52": info.get("fiftyTwoWeekHigh"),
                "Low52": info.get("fiftyTwoWeekLow"),
            }
        )
    except Exception:
        pass

    fund_cache[symbol] = result
    return result