import re
import os
import uuid

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from werkzeug.utils import secure_filename

from models import Alert, Notification, SearchHistory, User, UserProfile, Watchlist, db


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


@profile_bp.route("/api/data", methods=["GET"])
@login_required
def api_data():
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    watchlists = Watchlist.query.filter_by(user_id=current_user.id).all()
    alerts = Alert.query.filter_by(user_id=current_user.id).all()
    history = SearchHistory.query.filter_by(user_id=current_user.id).order_by(SearchHistory.searched_at.desc()).limit(8).all()
    
    total_stocks = sum(len(w.items) for w in watchlists)
    active_alerts = sum(1 for a in alerts if a.status == "active")
    
    watchlists_data = []
    for w in watchlists:
        watchlists_data.append({
            "id": w.id,
            "name": w.name,
            "is_default": w.is_default,
            "created_at": w.created_at.strftime("%Y-%m-%d") if w.created_at else "",
            "item_count": len(w.items)
        })
        
    alerts_data = []
    for a in alerts:
        alerts_data.append({
            "id": a.id,
            "name": a.name,
            "ticker": a.ticker or "Any",
            "condition_summary": a.condition_summary or "",
            "status": a.status,
            "trigger_count": a.trigger_count or 0,
            "last_triggered_at": a.last_triggered_at.isoformat() if hasattr(a.last_triggered_at, 'isoformat') and a.last_triggered_at else (str(a.last_triggered_at) if a.last_triggered_at else ""),
            "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else ""
        })
        
    history_data = []
    for h in history:
        history_data.append({
            "company": h.company,
            "exchange": h.exchange or "NSE",
            "searched_at": h.searched_at.strftime("%Y-%m-%d %H:%M") if h.searched_at else ""
        })
        
    notifications_history = []
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.id.desc()).limit(20).all()
    for n in notifications:
        notifications_history.append({
            "id": n.id,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime("%Y-%m-%d %H:%M") if n.created_at else ""
        })

    return jsonify({
        "user_id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": profile.full_name if profile else "",
        "member_since": current_user.created_at.strftime("%d %b %Y") if current_user.created_at else "Not available",
        "phone_number": profile.phone_number if profile else "",
        "whatsapp_number": profile.whatsapp_number if profile else "",
        "preferred_exchange": profile.preferred_exchange if profile else "NSE",
        "sms_enabled": profile.sms_enabled if profile else False,
        "two_factor_enabled": profile.two_factor_enabled if profile else False,
        "email_verified": getattr(current_user, "email_verified", True),
        "mobile_verified": profile.mobile_verified if profile else True,
        "stats": {
            "watchlists": len(watchlists),
            "tracked_stocks": total_stocks,
            "active_alerts": active_alerts
        },
        "watchlists": watchlists_data,
        "alerts": alerts_data,
        "history": history_data,
        "notifications": notifications_history
    })


@profile_bp.route("/api/update-account", methods=["POST"])
@login_required
def api_update_account():
    data = request.get_json() or {}
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
        
    full_name = data.get("full_name", "").strip()
    email = data.get("email", "").strip().lower()
    phone_number = data.get("phone_number", "").strip()
    whatsapp_number = data.get("whatsapp_number", "").strip()
    preferred_exchange = data.get("preferred_exchange", "NSE").strip()
    sms_enabled = bool(data.get("sms_enabled", False))
    
    if email and not re.match(EMAIL_REGEX, email):
        return jsonify({"error": "Enter a valid email address."}), 400
    if phone_number and not re.match(PHONE_REGEX, phone_number):
        return jsonify({"error": "Phone number must be exactly 10 digits."}), 400
        
    duplicate_user = User.query.filter(
        (User.email == email),
        User.id != current_user.id
    ).first()
    if duplicate_user:
        return jsonify({"error": "Email is already used by another account."}), 400
        
    current_user.email = email
    profile.full_name = full_name
    profile.phone_number = phone_number
    profile.whatsapp_number = whatsapp_number
    profile.preferred_exchange = preferred_exchange
    profile.sms_enabled = sms_enabled
    
    db.session.commit()
    return jsonify({"message": "Settings updated successfully."})


@profile_bp.route("/api/change-password", methods=["POST"])
@login_required
def api_change_password():
    data = request.get_json() or {}
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    
    from werkzeug.security import check_password_hash, generate_password_hash
    if not check_password_hash(current_user.password, current_password):
        return jsonify({"error": "Current password is incorrect."}), 400
        
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
        
    current_user.password = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Password updated successfully."})


@profile_bp.route("/api/toggle-2fa", methods=["POST"])
@login_required
def api_toggle_2fa():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled", False))
    
    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
        
    profile.two_factor_enabled = enabled
    db.session.commit()
    return jsonify({"message": f"2FA {'enabled' if enabled else 'disabled'} successfully.", "enabled": enabled})
