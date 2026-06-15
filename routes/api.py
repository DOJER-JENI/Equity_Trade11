
from flask import Blueprint, jsonify, request

from routes.main import global_df as df
from services.filter_engine import execute_screen, get_filter_metadata, get_filter_options
from services.live_market import get_live_quote, get_tradingview_symbol
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
    symbol = request.args.get("symbol", "")
    try:
        stock = lookup_stock(symbol)
        stock["app_company"] = to_app_company(symbol)
        return jsonify(stock)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Stock lookup failed: {exc}"}), 502
