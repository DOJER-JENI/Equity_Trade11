from __future__ import annotations

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Watchlist, WatchlistItem, db
from services.live_universe import build_live_universe
from services.live_market import get_market_status
from services.search_service import search_stocks


main_bp = Blueprint("main", __name__)

def _load_data():
    return build_live_universe()


global_df = _load_data()



def normalize_name(name: str) -> str:
    # Handle both standard tickers (RELIANCE, TCS) and compact symbols (TAJGVKHOTELS...)
    raw = str(name).strip().upper()
    # Remove .NS/.BO suffix if present
    base = raw.split(".")[0]
    # If the DataFrame has this exact company, use it
    if global_df is not None and not global_df.empty and base in global_df["Company"].values:
        return base
    # If not found, try to match by removing spaces from DataFrame Company values
    # (for compact symbols from search_service which stripped spaces)
    if global_df is not None and not global_df.empty:
        compact_base = "".join(base.split()).replace("&", "").replace(".", "")
        for company in global_df["Company"].unique():
            compact_company = "".join(str(company).upper().split()).replace("&", "").replace(".", "")
            if compact_company == compact_base:
                return company
    return base


def display_name(symbol: str) -> str:
    return str(symbol).strip().upper()


def get_company_choices():
    if global_df.empty:
        return []
    return sorted(global_df["Company"].dropna().unique().tolist())


def latest_rows_for_companies(companies: list[str]) -> list[dict]:
    if global_df.empty or not companies:
        return []

    filtered = global_df[global_df["Company"].isin(companies)]
    if filtered.empty:
        return []

    latest = filtered.sort_values("Date").groupby("Company").tail(1).copy()
    latest["DisplayName"] = latest["Company"].apply(display_name)
    return latest.to_dict(orient="records")


def get_company_snapshot(company: str):
    if global_df.empty:
        return None

    company_key = normalize_name(company)
    data = global_df[global_df["Company"] == company_key].sort_values("Date")

    if data.empty:
        return None

    return data


@main_bp.route("/")
def landing():
    return render_template("graphic.html")


@main_bp.route("/home")
@login_required
def home():
    watchlists = (
        Watchlist.query.filter_by(user_id=current_user.id)
        .order_by(Watchlist.created_at.desc(), Watchlist.id.desc())
        .all()
    )
    return render_template("home.html", watchlists=watchlists)


@main_bp.route("/watchlists", methods=["POST"])
@login_required
def create_watchlist():
    name = request.form.get("name", "").strip()

    if not name:
        watchlists = Watchlist.query.filter_by(user_id=current_user.id).all()
        return render_template(
            "home.html",
            watchlists=watchlists,
            error="Please enter a watchlist name.",
        )

    duplicate = Watchlist.query.filter(
        Watchlist.user_id == current_user.id,
        db.func.lower(Watchlist.name) == name.lower(),
    ).first()
    if duplicate:
        watchlists = Watchlist.query.filter_by(user_id=current_user.id).all()
        return render_template(
            "home.html",
            watchlists=watchlists,
            error="A watchlist with this name already exists.",
        )

    watchlist = Watchlist(user_id=current_user.id, name=name)
    db.session.add(watchlist)
    db.session.commit()

    return redirect(url_for("main.manage_watchlist", watchlist_id=watchlist.id))


@main_bp.route("/watchlists/<int:watchlist_id>/manage")
@login_required
def manage_watchlist(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    return render_template(
        "watchlist_manage.html",
        watchlist=watchlist,
        companies=get_company_choices(),
    )


@main_bp.route("/watchlists/<int:watchlist_id>/companies", methods=["POST"])
@login_required
def add_watchlist_company(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    raw_companies = request.form.get("companies", "")
    names = [normalize_name(name) for name in raw_companies.split(",") if name.strip()]

    unique_names = []
    for name in names:
        if name and name not in unique_names:
            unique_names.append(name)

    existing = {item.company for item in watchlist.items}
    for company in unique_names:
        if company not in existing:
            db.session.add(WatchlistItem(watchlist_id=watchlist.id, company=company))

    db.session.commit()
    return redirect(url_for("main.manage_watchlist", watchlist_id=watchlist.id))


@main_bp.route(
    "/watchlists/<int:watchlist_id>/companies/<int:item_id>/delete",
    methods=["POST"],
)
@login_required
def delete_watchlist_company(watchlist_id, item_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    item = WatchlistItem.query.filter_by(
        id=item_id, watchlist_id=watchlist.id
    ).first_or_404()

    db.session.delete(item)
    db.session.commit()

    return redirect(url_for("main.manage_watchlist", watchlist_id=watchlist.id))


@main_bp.route("/watchlists/<int:watchlist_id>/table")
@login_required
def watchlist_table(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    companies = [item.company for item in watchlist.items]
    data = latest_rows_for_companies(companies)

    return render_template("table.html", watchlist=watchlist, data=data)


@main_bp.route("/chart/<company>")
@login_required
def chart(company):
    data = get_company_snapshot(company)

    if data is None:
        return render_template(
            "chart.html",
            company=normalize_name(company),
            missing=True,
        )

    latest = data.iloc[-1]
    previous = data.iloc[-2] if len(data) > 1 else latest
    company_key = normalize_name(company)
    dma50_prev = previous.get("SMA50")
    dma200_series = data["Close"].rolling(200, min_periods=1).mean()
    dma200_prev = dma200_series.iloc[-2] if len(dma200_series) > 1 else dma200_series.iloc[-1]
    high_low = {
        "high": latest.get("High52") or latest.get("High"),
        "low": latest.get("Low52") or latest.get("Low"),
    }

    # Lookup proper company name from search universe
    search_results = search_stocks(company_key, limit=1)
    company_display_name = display_name(company_key)
    if search_results:
        company_display_name = search_results[0].get("name", company_display_name)

    return render_template(
        "chart.html",
        missing=False,
        company=company_key,
        company_name=company_display_name,
        current_price=latest.get("Close"),
        prev_close=previous.get("Close"),
        bse_symbol=f"{company_key}.BO",
        nse_symbol=company_key,
        company_site=f"https://www.google.com/search?q={company_key}+company+website",
        dma50_prev=dma50_prev,
        dma200_prev=dma200_prev,
        high_low=high_low,
        summary="A focused company page with key ratios, price trend, and quick Screener-style scanning.",
        dates=data["Date"].dt.strftime("%Y-%m-%d").tolist(),
        open=data["Open"].fillna(0).tolist(),
        high=data["High"].fillna(0).tolist(),
        low=data["Low"].fillna(0).tolist(),
        close=data["Close"].fillna(0).tolist(),
        volume=data["Volume"].fillna(0).tolist(),
        rsi=data["RSI"].fillna(0).tolist(),
        sma20=data["SMA20"].fillna(0).tolist(),
        sma50=data["SMA50"].fillna(0).tolist(),
        pe_series=data["PE"].ffill().fillna(0).tolist(),
        eps_series=data["EPS"].ffill().fillna(0).tolist(),
        latest=latest,
        companies=get_company_choices(),
    )


@main_bp.route("/description/<company>")
@login_required
def description(company):
    return redirect(url_for("main.chart", company=company))


@main_bp.route("/compare-multiple")
@login_required
def compare_multiple():
    companies = [
        normalize_name(c)
        for c in request.args.get("companies", "").split(",")
        if c.strip()
    ]

    rows = latest_rows_for_companies(companies)

    result = []
    for row in rows:
        rsi = float(row.get("RSI") or 0)
        sma20 = float(row.get("SMA20") or 0)
        sma50 = float(row.get("SMA50") or 0)
        close = float(row.get("Close") or 0)

        if rsi > 70:
            signal = "SELL"
        elif rsi < 30:
            signal = "BUY"
        else:
            signal = "HOLD"

        result.append(
            {
                "Company": row["Company"],
                "RSI": round(rsi, 2),
                "SMA20": round(sma20, 2),
                "SMA50": round(sma50, 2),
                "Trend": "UP" if close >= sma20 else "DOWN",
                "Signal": signal,
            }
        )

    return render_template("comparison_table.html", data=result)


@main_bp.route("/watchlist-data")
@login_required
def watchlist_data():
    companies = [
        normalize_name(c)
        for c in request.args.get("companies", "").split(",")
        if c.strip()
    ]
    return jsonify({"data": latest_rows_for_companies(companies)})


@main_bp.route("/dashboard")
@login_required
def dashboard():
    latest = []
    if not global_df.empty:
        ranked = global_df.sort_values(["Company", "Date"]).copy()
        ranked["ChangePct"] = ranked.groupby("Company")["Close"].pct_change().fillna(0) * 100
        latest_df = ranked.groupby("Company").tail(1).copy()
        latest = latest_df.to_dict(orient="records")

    watchlist = Watchlist.query.filter_by(user_id=current_user.id, is_default=True).first()
    if not watchlist:
        watchlist = Watchlist.query.filter_by(user_id=current_user.id).order_by(Watchlist.created_at.desc()).first()

    watchlist_rows = latest_rows_for_companies([item.company for item in watchlist.items]) if watchlist else []
    total_watchlists = Watchlist.query.filter_by(user_id=current_user.id).count()
    total_stocks = sum(len(w.items) for w in Watchlist.query.filter_by(user_id=current_user.id).all())

    gainers = sorted(latest, key=lambda row: float(row.get("ChangePct") or 0), reverse=True)[:5]
    losers = sorted(latest, key=lambda row: float(row.get("ChangePct") or 0))[:5]

    return render_template(
        "dashboard.html",
        market=get_market_status(),
        stats={
            "watchlists": total_watchlists,
            "stocks": total_stocks,
            "universe": len(get_company_choices()),
        },
        default_watchlist=watchlist,
        watchlist_rows=watchlist_rows,
        gainers=gainers,
        losers=losers,
    )


@main_bp.route("/screener")
@login_required
def screener():
    return render_template("screener.html")


@main_bp.route("/top-movers")
@login_required
def top_movers_page():
    return render_template("top_movers.html")

@main_bp.route("/alerts")
@login_required
def alerts_page():
    return redirect(url_for("main.dashboard") + "#alerts")


@main_bp.route("/api/top-movers-json")
@login_required
def top_movers_json():
    latest = []
    if not global_df.empty:
        ranked = global_df.sort_values(["Company", "Date"]).copy()
        ranked["ChangePct"] = ranked.groupby("Company")["Close"].pct_change().fillna(0) * 100
        latest_df = ranked.groupby("Company").tail(1).copy()
        latest = latest_df.to_dict(orient="records")

    gainers = sorted(latest, key=lambda row: float(row.get("ChangePct") or 0), reverse=True)[:5]
    losers = sorted(latest, key=lambda row: float(row.get("ChangePct") or 0))[:5]
    
    return jsonify({
        "gainers": [
            {"Company": g["Company"], "ChangePct": g["ChangePct"]}
            for g in gainers
        ],
        "losers": [
            {"Company": l["Company"], "ChangePct": l["ChangePct"]}
            for l in losers
        ]
    })