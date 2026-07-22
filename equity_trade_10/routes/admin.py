from functools import wraps

from flask import Blueprint, abort, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import Alert, AppSetting, AuditLog, Notification, User, db


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


@admin_bp.route("/")
@admin_required
def dashboard():
    stats = {
        "users": User.query.count(),
        "alerts": Alert.query.count(),
        "notifications": Notification.query.count(),
        "active_alerts": Alert.query.filter_by(status="active").count(),
    }
    recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
    return render_template("admin/dashboard.html", stats=stats, recent_logs=recent_logs)


@admin_bp.route("/users")
@admin_required
def users():
    items = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=items)


@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@admin_required
def toggle_admin(user_id):
    user = User.query.get_or_404(user_id)
    user.is_admin = not user.is_admin
    db.session.commit()
    return redirect(url_for("admin.users"))


@admin_bp.route("/alerts")
@admin_required
def alerts():
    items = Alert.query.order_by(Alert.created_at.desc()).all()
    return render_template("admin/alerts.html", alerts=items)


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        for key in ["DATA_PROVIDER", "SMS_PROVIDER", "SMTP_HOST", "SMTP_USER"]:
            value = request.form.get(key, "")
            setting = AppSetting.query.filter_by(key=key).first()
            if not setting:
                setting = AppSetting(key=key)
                db.session.add(setting)
            setting.value = value
        db.session.commit()
        return redirect(url_for("admin.settings"))

    settings_map = {s.key: s.value for s in AppSetting.query.all()}
    return render_template("admin/settings.html", settings=settings_map)


@admin_bp.route("/logs")
@admin_required
def logs():
    items = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()
    return render_template("admin/logs.html", logs=items)
