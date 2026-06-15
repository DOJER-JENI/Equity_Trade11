import sqlite3

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import AppSetting, User, db
from routes.admin import admin_bp
from routes.alerts import alerts_bp
from routes.api import api_bp
from routes.auth import auth_bp
from routes.main import main_bp
from routes.profile import profile_bp
from routes.trades import trades_bp
from routes.watchlists import watchlists_bp
from services.alert_worker import start_scheduler
from routes.admin_auth import admin_auth_bp




app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth_bp)
app.register_blueprint(main_bp)
app.register_blueprint(api_bp)
app.register_blueprint(alerts_bp)
app.register_blueprint(watchlists_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(trades_bp)
app.register_blueprint(admin_auth_bp)


def init_alert_db():
    conn = sqlite3.connect("alerts.db")
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS price_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            target_price REAL NOT NULL,
            condition_type TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            triggered_at TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def seed_settings():
    defaults = {
        "DATA_PROVIDER": "Yahoo Finance",
        "SMS_PROVIDER": "Console",
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_USER": "",
        "TEST_MARKET_ENABLED": "false",
        "TEST_MARKET_PROVIDER": "PaperTrade",
    }
    for key, value in defaults.items():
        if not AppSetting.query.filter_by(key=key).first():
            db.session.add(AppSetting(key=key, value=value))
    db.session.commit()


def init_schema_upgrades():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(user_profile)")
    profile_columns = {row[1] for row in cur.fetchall()}
    if "whatsapp_number" not in profile_columns:
        cur.execute("ALTER TABLE user_profile ADD COLUMN whatsapp_number VARCHAR(30)")
    if "profile_photo_url" not in profile_columns:
        cur.execute("ALTER TABLE user_profile ADD COLUMN profile_photo_url TEXT")
    cur.execute("PRAGMA table_info(cached_stock)")
    conn.commit()
    conn.close()


with app.app_context():
    db.create_all()
    init_schema_upgrades()
    seed_settings()
    init_alert_db()
    start_scheduler()

@app.route("/check-users")
def check_users():
    users = User.query.all()

    output = ""

    for u in users:
        output += f"""
        ID: {u.id}<br>
        Email: {u.email}<br>
        Username: {u.username}<br>
        Is Admin: {u.is_admin}<br><hr>
        """

    return output


for rule in app.url_map.iter_rules():
    print(rule.endpoint)

@app.route("/make-admin/<email>")
def make_admin(email):
    user = User.query.filter_by(email=email).first()

    if not user:
        return "User not found"

    user.is_admin = True
    db.session.commit()

    return f"{email} is now admin"

if __name__ == "__main__":
    app.run(debug=True)
