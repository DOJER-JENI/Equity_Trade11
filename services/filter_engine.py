from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
SCREENER_DB_PATH = BASE_DIR / "screener.db"

FIELD_SPECS = {
    "company": {"type": "string"},
    "last_price": {"type": "number"},
    "pct_change": {"type": "number"},
    "volume": {"type": "number"},
    "avg_volume_20d": {"type": "number"},
    "volume_ratio": {"type": "number"},
    "week_52_high": {"type": "number"},
    "week_52_low": {"type": "number"},
    "market_cap": {"type": "number"},
    "pe_ratio": {"type": "number"},
    "forward_pe": {"type": "number"},
    "eps": {"type": "number"},
    "eps_growth_yoy": {"type": "number"},
    "revenue_growth_yoy": {"type": "number"},
    "profit_margin": {"type": "number"},
    "roe": {"type": "number"},
    "debt_to_equity": {"type": "number"},
    "dividend_yield": {"type": "number"},
    "pb_ratio": {"type": "number"},
    "rsi_14": {"type": "number"},
    "macd_line": {"type": "number"},
    "macd_signal": {"type": "number"},
    "macd_histogram": {"type": "number"},
    "ema_20": {"type": "number"},
    "ema_50": {"type": "number"},
    "ema_200": {"type": "number"},
    "bb_upper": {"type": "number"},
    "bb_lower": {"type": "number"},
    "bb_pct": {"type": "number"},
    "sector": {"type": "string"},
    "industry": {"type": "string"},
    "exchange": {"type": "string"},
    "country": {"type": "string"},
    "index_member": {"type": "string"},
    "date": {"type": "string"},
}

ALLOWED_FIELDS = set(FIELD_SPECS.keys())
ALLOWED_OPS = {"=", "!=", "<", "<=", ">", ">=", "BETWEEN", "IN"}
DEFAULT_SORT = "volume"


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df


def prepare_screener_dataframe(source_df: pd.DataFrame) -> pd.DataFrame:
    if source_df is None or source_df.empty:
        return pd.DataFrame(columns=list(ALLOWED_FIELDS))

    df = source_df.copy()
    df = _ensure_columns(
        df,
        [
            "Date",
            "Company",
            "Close",
            "Volume",
            "High52",
            "Low52",
            "MarketCap",
            "PE",
            "EPS",
            "ROE",
            "RSI",
            "EMA20",
            "EMA50",
            "MACD",
            "MACD_SIGNAL",
        ],
    )

    df = df.sort_values(["Company", "Date"]).copy()

    df["pct_change"] = df.groupby("Company")["Close"].pct_change() * 100
    df["avg_volume_20d"] = (
        df.groupby("Company")["Volume"].transform(lambda x: x.rolling(20, min_periods=1).mean())
    )
    df["volume_ratio"] = df["Volume"] / df["avg_volume_20d"].replace(0, pd.NA)

    df["ema_200_calc"] = (
        df.groupby("Company")["Close"].transform(lambda x: x.ewm(span=200, adjust=False).mean())
    )
    df["macd_histogram"] = df["MACD"] - df["MACD_SIGNAL"]

    latest = df.groupby("Company").tail(1).copy()

    screener_df = pd.DataFrame(
        {
            "company": latest["Company"].astype(str),
            "last_price": latest["Close"],
            "pct_change": latest["pct_change"],
            "volume": latest["Volume"],
            "avg_volume_20d": latest["avg_volume_20d"],
            "volume_ratio": latest["volume_ratio"],
            "week_52_high": latest["High52"],
            "week_52_low": latest["Low52"],
            "market_cap": latest["MarketCap"],
            "pe_ratio": latest["PE"],
            "forward_pe": None,
            "eps": latest["EPS"],
            "eps_growth_yoy": None,
            "revenue_growth_yoy": None,
            "profit_margin": None,
            "roe": latest["ROE"],
            "debt_to_equity": None,
            "dividend_yield": None,
            "pb_ratio": None,
            "rsi_14": latest["RSI"],
            "macd_line": latest["MACD"],
            "macd_signal": latest["MACD_SIGNAL"],
            "macd_histogram": latest["macd_histogram"],
            "ema_20": latest["EMA20"],
            "ema_50": latest["EMA50"],
            "ema_200": latest["ema_200_calc"],
            "bb_upper": None,
            "bb_lower": None,
            "bb_pct": None,
            "sector": None,
            "industry": None,
            "exchange": "NSE",
            "country": "India",
            "index_member": None,
            "date": latest["Date"].astype(str),
        }
    )

    for field, spec in FIELD_SPECS.items():
        if field not in screener_df.columns:
            screener_df[field] = None

        if spec["type"] == "number":
            screener_df[field] = pd.to_numeric(screener_df[field], errors="coerce")

    return screener_df[list(ALLOWED_FIELDS)].copy()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SCREENER_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_stocks_table(source_df: pd.DataFrame) -> None:
    screener_df = prepare_screener_dataframe(source_df)

    conn = get_conn()
    screener_df.to_sql("stocks", conn, if_exists="replace", index=False)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_company ON stocks(company)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rsi_14 ON stocks(rsi_14)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pe_ratio ON stocks(pe_ratio)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_volume ON stocks(volume)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sector ON stocks(sector)")
    conn.commit()
    conn.close()


def _validate_single_value(field: str, value):
    field_type = FIELD_SPECS[field]["type"]

    if field_type == "number":
        if value is None:
            raise ValueError(f"Field '{field}' requires a numeric value")
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Field '{field}' requires a numeric value")

    if value is None:
        raise ValueError(f"Field '{field}' requires a non-empty value")

    return str(value)


def validate_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    logic = str(payload.get("logic", "AND")).upper()
    if logic not in {"AND", "OR"}:
        raise ValueError("logic must be AND or OR")

    sort_by = payload.get("sort_by", DEFAULT_SORT)
    if sort_by not in ALLOWED_FIELDS:
        sort_by = DEFAULT_SORT

    sort_dir = str(payload.get("sort_dir", "DESC")).upper()
    sort_dir = "ASC" if sort_dir == "ASC" else "DESC"

    try:
        limit = min(max(int(payload.get("limit", 100)), 1), 500)
    except (TypeError, ValueError):
        raise ValueError("limit must be a number")

    conditions = payload.get("conditions", [])
    if not isinstance(conditions, list):
        raise ValueError("conditions must be an array")

    cleaned_conditions = []

    for c in conditions:
        if not isinstance(c, dict):
            raise ValueError("Each condition must be an object")

        field = c.get("field")
        op = str(c.get("operator", "")).upper()
        value = c.get("value")

        if field not in ALLOWED_FIELDS:
            raise ValueError(f"Bad field: {field}")

        if op not in ALLOWED_OPS:
            raise ValueError(f"Bad operator: {op}")

        if op == "BETWEEN":
            if not isinstance(value, dict) or "min" not in value or "max" not in value:
                raise ValueError(f"BETWEEN for '{field}' requires value.min and value.max")
            min_val = _validate_single_value(field, value["min"])
            max_val = _validate_single_value(field, value["max"])
            cleaned_value = {"min": min_val, "max": max_val}

        elif op == "IN":
            if not isinstance(value, list) or not value:
                raise ValueError(f"IN for '{field}' requires a non-empty array")
            cleaned_value = [_validate_single_value(field, item) for item in value]

        else:
            cleaned_value = _validate_single_value(field, value)

        cleaned_conditions.append(
            {
                "field": field,
                "operator": op,
                "value": cleaned_value,
            }
        )

    return {
        "logic": logic,
        "conditions": cleaned_conditions,
        "sort_by": sort_by,
        "sort_dir": sort_dir,
        "limit": limit,
    }


def build_screen_query(payload: dict) -> tuple[str, list]:
    payload = validate_payload(payload)

    logic = payload["logic"]
    sort_by = payload["sort_by"]
    sort_dir = payload["sort_dir"]
    limit = payload["limit"]

    clauses = []
    params = []

    for c in payload["conditions"]:
        field = c["field"]
        op = c["operator"]
        value = c["value"]

        if op == "BETWEEN":
            clauses.append(f"{field} BETWEEN ? AND ?")
            params.extend([value["min"], value["max"]])

        elif op == "IN":
            placeholders = ",".join(["?"] * len(value))
            clauses.append(f"{field} IN ({placeholders})")
            params.extend(value)

        else:
            clauses.append(f"{field} {op} ?")
            params.append(value)

    where = f" WHERE {f' {logic} '.join(clauses)}" if clauses else ""
    sql = (
        "SELECT company, last_price, pct_change, volume, avg_volume_20d, volume_ratio, "
        "week_52_high, week_52_low, market_cap, pe_ratio, eps, roe, "
        "rsi_14, macd_line, macd_signal, macd_histogram, "
        "ema_20, ema_50, ema_200, sector, industry, exchange, country, date "
        f"FROM stocks{where} ORDER BY {sort_by} {sort_dir} LIMIT {limit}"
    )
    return sql, params


def execute_screen(payload: dict, source_df: pd.DataFrame) -> dict:
    sync_stocks_table(source_df)
    sql, params = build_screen_query(payload)

    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    data = [dict(row) for row in rows]
    return {
        "count": len(data),
        "generated_at": utc_timestamp(),
        "data": data,
    }


def get_filter_options(field: str, source_df: pd.DataFrame) -> list[str]:
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"Bad field: {field}")

    if FIELD_SPECS[field]["type"] != "string":
        raise ValueError(f"Field '{field}' is not a categorical filter")

    sync_stocks_table(source_df)

    conn = get_conn()
    rows = conn.execute(
        f"SELECT DISTINCT {field} AS value FROM stocks WHERE {field} IS NOT NULL AND TRIM({field}) != '' ORDER BY {field} ASC"
    ).fetchall()
    conn.close()

    return [row["value"] for row in rows if row["value"] is not None]


def get_filter_metadata() -> dict:
    return {
        "logic": ["AND", "OR"],
        "operators": sorted(ALLOWED_OPS),
        "fields": {
            "price_volume": [
                "last_price",
                "pct_change",
                "volume",
                "avg_volume_20d",
                "volume_ratio",
                "week_52_high",
                "week_52_low",
                "market_cap",
            ],
            "technical": [
                "rsi_14",
                "macd_line",
                "macd_signal",
                "macd_histogram",
                "ema_20",
                "ema_50",
                "ema_200",
                "bb_upper",
                "bb_lower",
                "bb_pct",
            ],
            "fundamentals": [
                "pe_ratio",
                "forward_pe",
                "eps",
                "eps_growth_yoy",
                "revenue_growth_yoy",
                "profit_margin",
                "roe",
                "debt_to_equity",
                "dividend_yield",
                "pb_ratio",
            ],
            "sector_exchange": [
                "sector",
                "industry",
                "exchange",
                "country",
                "index_member",
            ],
        },
    }
