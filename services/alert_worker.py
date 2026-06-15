import json
import sqlite3
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from routes.main import global_df
from config import Config
from services.email_service import send_alert_email
from services.filter_engine import build_screen_query, get_conn as get_screener_conn, sync_stocks_table


scheduler = None


def get_conn():
    conn = sqlite3.connect("alerts.db", timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def fire_alert(alert, matches, conn):
    preview = ", ".join(
        str(row["company"]) for row in matches[:5] if row["company"]
    )
    message = f"Alert '{alert['name']}' matched: {preview}"
    channel_sent = False

    if alert["notify_email"]:
        try:
            user_conn = sqlite3.connect(Config.SQLALCHEMY_DATABASE_URI.replace("sqlite:///", ""))
            user_conn.row_factory = sqlite3.Row
            user = user_conn.execute("SELECT email FROM user WHERE id = ?", (alert["user_id"],)).fetchone()
            user_conn.close()
            if user and user["email"]:
                channel_sent = send_alert_email(user["email"], message)
        except Exception as exc:
            print("Alert email failed:", exc)
    elif alert["notify_sms"]:
        print(f"SMS alert queued once: {message}")
        channel_sent = True
    elif alert["notify_whatsapp"]:
        print(f"WhatsApp alert queued once: {message}")
        channel_sent = True

    conn.execute(
        """
        INSERT INTO notifications (user_id, alert_id, message, payload, is_read, created_at)
        VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
        """,
        (
            alert["user_id"],
            alert["id"],
            message,
            json.dumps([dict(row) for row in matches], default=str),
        ),
    )

    conn.execute(
        """
        UPDATE alerts
        SET last_triggered_at = ?, trigger_count = COALESCE(trigger_count, 0) + 1
        WHERE id = ?
        """,
        (utc_now_iso(), alert["id"]),
    )


def evaluate_alerts():
    sync_stocks_table(global_df)

    conn = get_conn()
    alerts = conn.execute(
        "SELECT * FROM alerts WHERE status = 'active'"
    ).fetchall()

    for alert in alerts:
        if alert["last_triggered_at"]:
            try:
                last = datetime.fromisoformat(alert["last_triggered_at"].replace("Z", "+00:00"))
                elapsed = datetime.now(timezone.utc) - last.astimezone(timezone.utc)
                if elapsed.total_seconds() < int(alert["cooldown_minutes"] or 60) * 60:
                    continue
            except Exception:
                pass

        payload = json.loads(alert["condition_json"] or "{}")
        payload.setdefault("conditions", [])
        payload["limit"] = 25

        if alert["ticker"]:
            payload["conditions"].append(
                {
                    "field": "company",
                    "operator": "=",
                    "value": alert["ticker"],
                }
            )

        try:
            sql, params = build_screen_query(payload)
            screener_conn = get_screener_conn()
            matches = screener_conn.execute(sql, params).fetchall()
            screener_conn.close()
        except Exception:
            continue

        if matches:
            fire_alert(alert, matches, conn)

    conn.commit()
    conn.close()


def start_scheduler():
    global scheduler

    if scheduler is not None:
        return scheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        evaluate_alerts,
        "interval",
        minutes=1,
        id="alert-evaluator",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
