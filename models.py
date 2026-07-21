from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email_verified = db.Column(db.Boolean, default=True, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reset_token = db.Column(db.String(120), unique=True)
    reset_token_expires_at = db.Column(db.DateTime)

    profile = db.relationship(
        "UserProfile",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    watchlists = db.relationship(
        "Watchlist",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )
    alerts = db.relationship(
        "Alert",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )
    notifications = db.relationship(
        "Notification",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )
    trade_orders = db.relationship(
        "TradeOrder",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )


class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    full_name = db.Column(db.String(150))
    phone_number = db.Column(db.String(30), unique=True)
    mobile_verified = db.Column(db.Boolean, default=True, nullable=False)
    whatsapp_number = db.Column(db.String(30))
    profile_photo_url = db.Column(db.Text)
    sms_enabled = db.Column(db.Boolean, default=False)
    preferred_exchange = db.Column(db.String(20), default="NSE")
    two_factor_enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Watchlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship(
        "WatchlistItem",
        backref="watchlist",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="WatchlistItem.company.asc()",
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_watchlist_user_name"),
    )


class WatchlistItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    watchlist_id = db.Column(db.Integer, db.ForeignKey("watchlist.id"), nullable=False)
    company = db.Column(db.String(50), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("watchlist_id", "company", name="uq_watchlist_company"),
    )


class SearchHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    company = db.Column(db.String(50), nullable=False)
    exchange = db.Column(db.String(10), default="NSE")
    searched_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "company", name="uq_search_history_user_company"),
    )


class CachedStock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(30), unique=True, nullable=False, index=True)
    exchange = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(120))
    last_price = db.Column(db.Float)
    previous_close = db.Column(db.Float)
    change = db.Column(db.Float)
    change_percent = db.Column(db.Float)
    day_high = db.Column(db.Float)
    day_low = db.Column(db.Float)
    volume = db.Column(db.Float)
    payload_json = db.Column(db.Text)
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    ticker = db.Column(db.String(30))
    condition_json = db.Column(db.Text, nullable=False)
    condition_summary = db.Column(db.Text)
    note = db.Column(db.Text)
    notify_email = db.Column(db.Boolean, default=False)
    notify_inapp = db.Column(db.Boolean, default=True)
    notify_sms = db.Column(db.Boolean, default=False)
    notify_whatsapp = db.Column(db.Boolean, default=False)
    cooldown_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.String(20), default="active")
    last_triggered_at = db.Column(db.DateTime)
    trigger_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    notifications = db.relationship(
        "Notification",
        backref="alert",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    alert_id = db.Column(db.Integer, db.ForeignKey("alert.id"))
    message = db.Column(db.Text, nullable=False)
    payload = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AlertHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    alert_id = db.Column(db.Integer, db.ForeignKey("alert.id"))
    message = db.Column(db.Text, nullable=False)
    payload = db.Column(db.Text)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)


class TradeOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    company = db.Column(db.String(50), nullable=False)
    side = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    order_type = db.Column(db.String(20), default="MARKET")
    note = db.Column(db.Text)
    status = db.Column(db.String(30), default="submitted")
    market_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AppSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    action = db.Column(db.String(150), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.String(50))
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
