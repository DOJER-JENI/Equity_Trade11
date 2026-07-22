import secrets
from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash

from models import User, db
from services.email_service import send_password_reset_email

try:
    from services.audit_logger import write_audit_log
except Exception:
    write_audit_log = None


admin_auth_bp = Blueprint("admin_auth", __name__, url_prefix="/admin")


def log_admin_action(action, user=None, details=None):
    if not write_audit_log:
        return
    try:
        write_audit_log(
            action,
            user.id if user else None,
            "AdminAuth",
            user.id if user else None,
            details,
        )
    except Exception:
        db.session.rollback()


@admin_auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated and getattr(current_user, "is_admin", False):
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash("Invalid admin email or password.", "error")
            log_admin_action("admin_login_failed", None, f"email={email}")
            return render_template("admin/login.html", email=email)

        if not user.is_admin:
            flash("This account does not have admin access.", "error")
            log_admin_action("admin_login_denied", user, "Non-admin account tried admin login")
            return render_template("admin/login.html", email=email)

        if hasattr(user, "is_active_user") and not user.is_active_user:
            flash("This admin account is inactive.", "error")
            log_admin_action("admin_login_inactive", user, "Inactive admin account")
            return render_template("admin/login.html", email=email)

        login_user(user, remember=remember)
        log_admin_action("admin_login_success", user, "Admin signed in")
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@admin_auth_bp.route("/logout")
@login_required
def logout():
    if getattr(current_user, "is_admin", False):
        log_admin_action("admin_logout", current_user, "Admin signed out")
    logout_user()
    flash("Admin logged out successfully.", "success")
    return redirect(url_for("admin_auth.login"))


@admin_auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email, is_admin=True).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=30)
            db.session.commit()
            reset_link = url_for("admin_auth.reset_password", token=token, _external=True)
            display_name = user.profile.full_name if user.profile and user.profile.full_name else user.username
            send_password_reset_email(user.email, display_name, reset_link)
            log_admin_action("admin_password_reset_requested", user, "Reset email requested")

        flash("If an admin account exists for this email, a reset link has been sent.", "success")
        return redirect(url_for("admin_auth.forgot_password"))

    return render_template("admin/forgot_password.html")


@admin_auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token, is_admin=True).first()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        flash("Admin reset link is invalid or expired.", "error")
        return redirect(url_for("admin_auth.forgot_password"))

    if request.method == "POST":
        from werkzeug.security import generate_password_hash

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("admin/reset_password.html", token=token)
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("admin/reset_password.html", token=token)

        user.password = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.commit()
        log_admin_action("admin_password_reset_completed", user, "Admin password changed")
        flash("Admin password reset successful. Please login.", "success")
        return redirect(url_for("admin_auth.login"))

    return render_template("admin/reset_password.html", token=token)