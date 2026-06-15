import re
import os
import uuid

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

from models import Alert, SearchHistory, User, UserProfile, Watchlist, db


profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

PHONE_REGEX = r"^\d{10}$"
EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
PHOTO_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


@profile_bp.route("/")
@login_required
def index():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    watchlists = (
        Watchlist.query.filter_by(user_id=current_user.id)
        .order_by(Watchlist.created_at.desc())
        .all()
    )
    alerts = (
        Alert.query.filter_by(user_id=current_user.id)
        .order_by(Alert.created_at.desc())
        .all()
    )
    history = (
        SearchHistory.query.filter_by(user_id=current_user.id)
        .order_by(SearchHistory.searched_at.desc())
        .limit(8)
        .all()
    )
    active_alerts = [alert for alert in alerts if alert.status == "active"]
    tracked_stocks = sum(len(watchlist.items) for watchlist in watchlists)
    stats = {
        "watchlists": len(watchlists),
        "tracked_stocks": tracked_stocks,
        "alerts": len(active_alerts),
        "saved_screens": len(history),
    }
    section = request.args.get("section", "dashboard")
    return render_template(
        "profile.html",
        profile=profile,
        watchlists=watchlists,
        alerts=alerts,
        history=history,
        stats=stats,
        section=section,
    )


@profile_bp.route("/account", methods=["POST"])
@login_required
def update_account():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    phone_number = request.form.get("phone_number", "").strip()
    whatsapp_number = request.form.get("whatsapp_number", "").strip()
    preferred_exchange = request.form.get("preferred_exchange", "NSE").strip()
    sms_enabled = request.form.get("sms_enabled") == "on"

    if not username:
        flash("Username is required.", "error")
        return redirect(url_for("profile.index", section="account"))
    if not re.match(EMAIL_REGEX, email):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("profile.index", section="account"))
    if phone_number and not re.match(PHONE_REGEX, phone_number):
        flash("Phone number must be exactly 10 digits.", "error")
        return redirect(url_for("profile.index", section="account"))

    duplicate_user = User.query.filter(
        ((User.username == username) | (User.email == email)),
        User.id != current_user.id,
    ).first()
    if duplicate_user:
        flash("Username or email is already used by another account.", "error")
        return redirect(url_for("profile.index", section="account"))

    duplicate_phone = UserProfile.query.filter(
        UserProfile.phone_number == phone_number,
        UserProfile.user_id != current_user.id,
    ).first()
    if phone_number and duplicate_phone:
        flash("This phone number is already used by another account.", "error")
        return redirect(url_for("profile.index", section="account"))

    photo = request.files.get("profile_photo")
    if photo and photo.filename:
        extension = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
        if extension not in PHOTO_EXTENSIONS:
            flash("Profile photo must be PNG, JPG, JPEG, or WEBP.", "error")
            return redirect(url_for("profile.index", section="account"))
        upload_dir = os.path.join("static", "uploads", "profiles")
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(f"user-{current_user.id}-{uuid.uuid4().hex}.{extension}")
        photo.save(os.path.join(upload_dir, filename))
        profile.profile_photo_url = url_for("static", filename=f"uploads/profiles/{filename}")

    current_user.username = username
    current_user.email = email
    profile.full_name = full_name
    profile.phone_number = phone_number
    profile.whatsapp_number = whatsapp_number
    profile.preferred_exchange = preferred_exchange
    profile.sms_enabled = sms_enabled
    db.session.commit()
    flash("Account settings updated successfully.", "success")
    return redirect(url_for("profile.index", section="account"))


@profile_bp.route("/save", methods=["POST"])
@login_required
def save():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    whatsapp_number = request.form.get("whatsapp_number", "").strip()
    preferred_exchange = request.form.get("preferred_exchange", "NSE").strip()
    sms_enabled = request.form.get("sms_enabled") == "on"

    if phone_number and not re.match(PHONE_REGEX, phone_number):
        flash("Phone number must be exactly 10 digits.", "error")
        return redirect(url_for("profile.index"))

    duplicate_phone = UserProfile.query.filter(
        UserProfile.phone_number == phone_number,
        UserProfile.user_id != current_user.id,
    ).first()
    if duplicate_phone:
        flash("This phone number is already used by another account.", "error")
        return redirect(url_for("profile.index"))

    profile.full_name = full_name
    profile.phone_number = phone_number
    profile.whatsapp_number = whatsapp_number
    profile.preferred_exchange = preferred_exchange
    profile.sms_enabled = sms_enabled
    db.session.commit()
    flash("Profile saved successfully.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    logout_user()
    if user:
        db.session.delete(user)
        db.session.commit()
    flash("Your account has been deleted successfully.", "success")
    return redirect(url_for("auth.register"))
