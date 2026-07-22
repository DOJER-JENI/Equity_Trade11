
from flask import Blueprint, jsonify, request

from routes.main import global_df as df
from services.filter_engine import execute_screen, get_filter_metadata, get_filter_options
from services.live_market import get_live_quote, get_tradingview_symbol
from services.search_service import find_symbol, search_stocks
from services.stock_lookup import lookup_stock, to_app_company



api_bp = Blueprint("api", __name__, url_prefix="/api")


def run_screen_engine(condition_payload):
    result = execute_screen(condition_payload, df)
    return result["data"]


@api_bp.route("/health")
def health():
    return jsonify({"status": "running"})


@api_bp.route("/screen", methods=["POST"])
def screen():
    payload = request.get_json() or {}

    try:
        result = execute_screen(payload, df)
        return jsonify(result)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Screening failed: {exc}"}), 500


@api_bp.route("/filter-metadata", methods=["GET"])
def filter_metadata():
    return jsonify(get_filter_metadata())


@api_bp.route("/filter-options/<field>", methods=["GET"])
def filter_options(field):
    try:
        return jsonify({"field": field, "options": get_filter_options(field, df)})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Failed to load filter options: {exc}"}), 500


@api_bp.route("/company-full/<name>")
def company_full(name):
    company = str(name).replace(" ", "").upper()
    company_df = df[df["Company"] == company].sort_values("Date")

    if company_df.empty:
        return jsonify({"error": "No data"}), 404

    latest = company_df.iloc[-1]
    previous = company_df.iloc[-2] if len(company_df) > 1 else latest

    return jsonify(
        {
            "Company": latest["Company"],
            "Price": latest.get("Close"),
            "MarketCap": latest.get("MarketCap"),
            "PE": latest.get("PE"),
            "BookValue": latest.get("BookValue"),
            "ROE": latest.get("ROE"),
            "ROA": latest.get("ROA"),
            "High52": latest.get("High52"),
            "Low52": latest.get("Low52"),
            "Volume": latest.get("Volume"),
            "PriceChange": (latest.get("Close") or 0) - (previous.get("Close") or 0),
        }
    )


@api_bp.route("/live-quote/<symbol>", methods=["GET"])
def live_quote(symbol):
    data = get_live_quote(symbol)
    if not data:
        return jsonify({"error": "Live quote not available"}), 404
    return jsonify(data)


@api_bp.route("/tradingview-symbol/<symbol>", methods=["GET"])
def tradingview_symbol(symbol):
    return jsonify(
        {
            "symbol": str(symbol).strip().upper(),
            "tradingview_symbol": get_tradingview_symbol(symbol),
        }
    )


@api_bp.route("/stock-search", methods=["GET"])
def stock_search():
    raw = request.args.get("symbol", "").strip()
    if not raw:
        return jsonify({"error": "Symbol is required"}), 400

    query = raw.upper()

    # 1. Search the static universe first for name, sector, exchange
    universe = search_stocks(query, limit=5)
    static_match = None
    for s in universe:
        if s["symbol"] == query:
            static_match = s
            break
    if static_match is None and universe:
        static_match = universe[0]

    # 2. Try to resolve via find_symbol for the base symbol
    resolved_symbol = find_symbol(raw)
    base_symbol = resolved_symbol or (static_match["symbol"] if static_match else query)

    # 3. Build the .NS symbol for live lookup
    nse_symbol = base_symbol.upper()
    if not nse_symbol.endswith(".NS") and not nse_symbol.endswith(".BO"):
        nse_symbol = nse_symbol + ".NS"

    # 4. Try live price lookup (best-effort)
    live_data = {}
    try:
        live_result = lookup_stock(nse_symbol)
        if live_result:
            live_data = {
                "price": live_result.get("price"),
                "previous_close": live_result.get("previous_close"),
                "day_high": live_result.get("day_high"),
                "day_low": live_result.get("day_low"),
                "volume": live_result.get("volume"),
                "fetched_at": live_result.get("fetched_at"),
                "updated_at": live_result.get("updated_at"),
            }
    except Exception:
        # yfinance failure — still return static data
        pass

    # 5. Merge static + live data — static always wins for name/sector/exchange
    result = {
        "symbol": base_symbol,
        "base_symbol": base_symbol,
        "name": (static_match or {}).get("name", base_symbol),
        "sector": (static_match or {}).get("sector", "Others"),
        "exchange": (static_match or {}).get("exchange", "NSE"),
        "app_company": base_symbol,
        **live_data,
    }

    return jsonify(result)


@api_bp.route("/autocomplete", methods=["GET"])
def autocomplete():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    # For short queries, return more results to surface popular stocks
    limit = 30 if len(q) <= 2 else 15
    results = search_stocks(q, limit=limit)
    return jsonify(results)
