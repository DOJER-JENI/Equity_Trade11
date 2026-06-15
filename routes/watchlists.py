from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Watchlist, WatchlistItem, db
from routes.main import get_company_choices, latest_rows_for_companies, normalize_name
from services.stock_lookup import lookup_stock, to_app_company


watchlists_bp = Blueprint("watchlists", __name__, url_prefix="/watchlists")


@watchlists_bp.route("/")
@login_required
def index():
    watchlists = (
        Watchlist.query.filter_by(user_id=current_user.id)
        .order_by(Watchlist.is_default.desc(), Watchlist.created_at.desc())
        .all()
    )
    return render_template("watchlists.html", watchlists=watchlists)


@watchlists_bp.route("/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name", "").strip()
    is_default = request.form.get("is_default") == "on"

    if not name:
        flash("Please enter a watchlist name.", "error")
        return redirect(url_for("watchlists.index"))

    duplicate = Watchlist.query.filter(
        Watchlist.user_id == current_user.id,
        db.func.lower(Watchlist.name) == name.lower(),
    ).first()
    if duplicate:
        flash("A watchlist with this name already exists.", "error")
        return redirect(url_for("watchlists.index"))

    if is_default:
        Watchlist.query.filter_by(user_id=current_user.id, is_default=True).update(
            {"is_default": False}
        )

    watchlist = Watchlist(
        user_id=current_user.id,
        name=name,
        is_default=is_default,
    )
    db.session.add(watchlist)
    db.session.commit()

    return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))


@watchlists_bp.route("/<int:watchlist_id>/rename", methods=["POST"])
@login_required
def rename(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()
    name = request.form.get("name", "").strip()

    if not name:
        flash("Watchlist name cannot be empty.", "error")
        return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))

    duplicate = Watchlist.query.filter(
        Watchlist.user_id == current_user.id,
        Watchlist.id != watchlist.id,
        db.func.lower(Watchlist.name) == name.lower(),
    ).first()
    if duplicate:
        flash("A watchlist with this name already exists.", "error")
        return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))

    watchlist.name = name
    db.session.commit()
    flash("Watchlist renamed.", "success")
    return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))


@watchlists_bp.route("/<int:watchlist_id>")
@login_required
def detail(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()
    companies = [item.company for item in watchlist.items]
    rows = latest_rows_for_companies(companies)

    return render_template(
        "watchlist_detail.html",
        watchlist=watchlist,
        companies_master=get_company_choices(),
        rows=rows,
    )


@watchlists_bp.route("/<int:watchlist_id>/add-company", methods=["POST"])
@login_required
def add_company(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    raw_companies = request.form.get("companies", "")
    names = []
    for raw_company in [x.strip().upper() for x in raw_companies.split(",") if x.strip()]:
        try:
            lookup_stock(raw_company)
            names.append(to_app_company(raw_company))
        except ValueError:
            flash(f"{raw_company} skipped. Use only .NS or .BO symbols.", "error")
        except Exception:
            flash(f"{raw_company} could not be fetched right now.", "error")

    existing = {item.company for item in watchlist.items}

    for company in names:
        if company and company not in existing:
            db.session.add(WatchlistItem(watchlist_id=watchlist.id, company=company))
            existing.add(company)

    db.session.commit()
    return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))


@watchlists_bp.route("/<int:watchlist_id>/remove-company/<int:item_id>", methods=["POST"])
@login_required
def remove_company(watchlist_id, item_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()
    item = WatchlistItem.query.filter_by(
        id=item_id, watchlist_id=watchlist.id
    ).first_or_404()

    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))


@watchlists_bp.route("/<int:watchlist_id>/delete", methods=["POST"])
@login_required
def delete_watchlist(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(watchlist)
    db.session.commit()
    return redirect(url_for("watchlists.index"))


@watchlists_bp.route("/default")
@login_required
def default_watchlist():
    watchlist = Watchlist.query.filter_by(
        user_id=current_user.id, is_default=True
    ).first()

    if not watchlist:
        watchlist = Watchlist(
            user_id=current_user.id,
            name="Default Watchlist",
            is_default=True,
        )
        db.session.add(watchlist)
        db.session.commit()

    return redirect(url_for("watchlists.detail", watchlist_id=watchlist.id))


@watchlists_bp.route("/api/<int:watchlist_id>/companies")
@login_required
def watchlist_companies_api(watchlist_id):
    watchlist = Watchlist.query.filter_by(
        id=watchlist_id, user_id=current_user.id
    ).first_or_404()

    return jsonify(
        {
            "id": watchlist.id,
            "name": watchlist.name,
            "companies": [item.company for item in watchlist.items],
        }
    )
