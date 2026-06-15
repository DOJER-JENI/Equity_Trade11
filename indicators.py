import pandas as pd


def calculate_rsi(close, period=14):
    delta = close.astype(float).diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def calculate_macd(close):
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal


def calculate_indicators(df):
    df = df.copy()
    df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
    df = df.sort_values(["Company", "Date"])

    df["RSI"] = df.groupby("Company")["Close"].transform(calculate_rsi)
    df["SMA20"] = df.groupby("Company")["Close"].transform(
        lambda x: x.rolling(window=20).mean()
    )
    df["SMA50"] = df.groupby("Company")["Close"].transform(
        lambda x: x.rolling(window=50).mean()
    )
    df["EMA20"] = df.groupby("Company")["Close"].transform(
        lambda x: x.ewm(span=20, adjust=False).mean()
    )
    df["EMA50"] = df.groupby("Company")["Close"].transform(
        lambda x: x.ewm(span=50, adjust=False).mean()
    )
    df["High52"] = df.groupby("Company")["Close"].transform(
        lambda x: x.rolling(window=252, min_periods=1).max()
    )
    df["Low52"] = df.groupby("Company")["Close"].transform(
        lambda x: x.rolling(window=252, min_periods=1).min()
    )
    macd, signal = calculate_macd(df["Close"])
    df["MACD"] = macd
    df["MACD_SIGNAL"] = signal
    return df