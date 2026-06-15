import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import User, UserProfile, db
from services.email_service import send_password_reset_email, send_welcome_email


auth_bp = Blueprint("auth", __name__)

EMAIL_REGEX = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
PHONE_REGEX = r"^\d{10}$"


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = full_name or request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone_number = request.form.get("phone_number", "").strip()
        password_raw = request.form.get("password", "")

        if not full_name:
            flash("Full name is required.", "error")
            return render_template("register.html")

        if not re.match(EMAIL_REGEX, email):
            flash("Enter a valid email address.", "error")
            return render_template("register.html")

        if not re.match(PHONE_REGEX, phone_number):
            flash("Phone number must be exactly 10 digits.", "error")
            return render_template("register.html")

        if len(password_raw) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        if User.query.filter_by(email=email).first():
            flash("This email is already registered.", "error")
            return render_template("register.html")

        generated_username = username.lower().replace(" ", "")
        original_username = generated_username
        counter = 1
        while User.query.filter_by(username=generated_username).first():
            generated_username = f"{original_username}{counter}"
            counter += 1

        if UserProfile.query.filter_by(phone_number=phone_number).first():
            flash("This phone number is already registered.", "error")
            return render_template("register.html")

        # user = User(
        #     username=generated_username,
        #     email=email,
        #     password=generate_password_hash(password_raw),
        #     email_verified=True,
        # )
        user = User(
            username=generated_username,
            email=email,
            password=generate_password_hash(password_raw)
        )
        db.session.add(user)
        db.session.flush()

        # profile = UserProfile(
        #     user_id=user.id,
        #     full_name=full_name,
        #     phone_number=phone_number,
        #     sms_enabled=False,
        #     preferred_exchange="NSE"
        # )
        profile = UserProfile(
            user_id=user.id,
            full_name=full_name,
            phone_number=phone_number,
            mobile_verified=True,
            sms_enabled=False,
            preferred_exchange="NSE",
        )
        db.session.add(profile)
        db.session.commit()

        send_welcome_email(email, full_name)
        flash("Signup successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.", "error")
        return render_template("login.html")

    return render_template("login.html")


@auth_bp.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email, is_admin=True).first()

        if user and check_password_hash(user.password, password):
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid admin email or password.", "error")
        return render_template("login.html", admin_mode=True)

    return render_template("login.html", admin_mode=True)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not re.match(EMAIL_REGEX, email):
            flash("Enter a valid email address.", "error")
            return render_template("forgot_password.html")

        user = User.query.filter_by(email=email).first()

        if user:
            token = secrets.token_urlsafe(32)
            user.reset_token = token
            user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=30)
            db.session.commit()

            reset_link = url_for("auth.reset_password", token=token, _external=True)
            profile_name = user.profile.full_name if user.profile and user.profile.full_name else user.username
            send_password_reset_email(user.email, profile_name, reset_link)

        flash("If the email exists, a reset link has been sent.", "success")
        return redirect(url_for("auth.forgot_password"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()

    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        flash("Reset link is invalid or expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("reset_password.html", token=token)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token)

        user.password = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expires_at = None
        db.session.commit()

        flash("Password reset successful. Please login.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)

from flask_login import current_user, login_required

@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not check_password_hash(current_user.password, current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("profile.index", section="security"))

    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for("profile.index", section="security"))

    if len(new_password) < 8:
        flash("Password must be at least 8 characters.", "error")
        return redirect(url_for("profile.index", section="security"))

    current_user.password = generate_password_hash(new_password)
    db.session.commit()

    flash("Password changed successfully.", "success")
    return redirect(url_for("profile.index", section="security"))


@auth_bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
