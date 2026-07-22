import json
import sqlite3
from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.filter_engine import validate_payload


alerts_bp = Blueprint("alerts", __name__, url_prefix="/api")


def get_conn():
    conn = sqlite3.connect("users.db", timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def summarize_condition(payload: dict, ticker: str | None) -> str:
    conditions = payload.get("conditions", [])
    if not conditions:
        return f"Alert for {ticker or 'market'}"

    parts = []
    for cond in conditions[:3]:
        field = cond.get("field", "")
        op = cond.get("operator", "")
        value = cond.get("value")

        if op == "BETWEEN" and isinstance(value, dict):
            val_text = f"{value.get('min')} to {value.get('max')}"
        elif op == "IN" and isinstance(value, list):
            val_text = ", ".join(str(v) for v in value[:3])
        else:
            val_text = str(value)

        parts.append(f"{field} {op} {val_text}")

    prefix = ticker or "Any stock"
    return f"{prefix}: {' AND '.join(parts)}"


@alerts_bp.route("/alerts", methods=["POST"])
@login_required
def create_alert():
    data = request.get_json() or {}

    name = str(data.get("name", "")).strip()
    ticker = str(data.get("ticker", "")).strip().upper() or None
    condition = data.get("condition", {})
    channel = str(data.get("channel", "")).strip().lower()
    notify_email = 1 if channel == "email" else 0
    notify_sms = 1 if channel == "sms" else 0
    notify_whatsapp = 1 if channel == "whatsapp" else 0
    notify_inapp = 1 if data.get("notify_inapp", True) else 0
    cooldown_minutes = int(data.get("cooldown_minutes", 60))
    note = str(data.get("note", "")).strip()

    if not name:
        return jsonify({"error": "Alert name is required"}), 400

    try:
        validated = validate_payload(condition)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    summary = summarize_condition(validated, ticker)
    conn = get_conn()
    cur = conn.cursor()
    duplicate = cur.execute(
        """
        SELECT id FROM alert
        WHERE user_id = ? AND COALESCE(ticker, '') = COALESCE(?, '')
          AND condition_summary = ? AND status = 'active'
        """,
        (current_user.id, ticker, summary),
    ).fetchone()
    if duplicate:
        conn.close()
        return jsonify({"error": "Duplicate alert for the same stock condition is not allowed."}), 409

    cur.execute(
        """
        INSERT INTO alert (
            user_id, name, ticker, condition_json, condition_summary,
            note, notify_email, notify_sms, notify_whatsapp, notify_inapp, cooldown_minutes, status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
        """,
        (
            current_user.id,
            name,
            ticker,
            json.dumps(validated),
            summary,
            note,
            notify_email,
            notify_sms,
            notify_whatsapp,
            notify_inapp,
            cooldown_minutes,
        ),
    )
    conn.commit()
    alert_id = cur.lastrowid
    alert = conn.execute("SELECT * FROM alert WHERE id = ?", (alert_id,)).fetchone()
    conn.close()

    return jsonify({"message": "Alert created", "alert": dict(alert)}), 201


@alerts_bp.route("/alerts", methods=["GET"])
@login_required
def list_alerts():
    ticker = request.args.get("ticker")
    status = request.args.get("status", "")

    conn = get_conn()

    sql = "SELECT * FROM alert WHERE user_id = ?"
    params = [current_user.id]

    if status:
        sql += " AND status = ?"
        params.append(status)

    if ticker:
        sql += " AND (ticker = ? OR ticker IS NULL)"
        params.append(ticker.upper().strip())

    sql += " ORDER BY id DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@alerts_bp.route("/alerts/<int:alert_id>", methods=["PATCH"])
@login_required
def update_alert(alert_id):
    data = request.get_json() or {}
    action = str(data.get("action", "")).strip().lower()

    conn = get_conn()
    alert = conn.execute(
        "SELECT * FROM alert WHERE id = ? AND user_id = ?",
        (alert_id, current_user.id),
    ).fetchone()

    if not alert:
        conn.close()
        return jsonify({"error": "Alert not found"}), 404

    if action == "pause":
        conn.execute("UPDATE alert SET status = 'paused' WHERE id = ?", (alert_id,))
    elif action == "resume":
        conn.execute("UPDATE alert SET status = 'active' WHERE id = ?", (alert_id,))
    elif action == "delete":
        conn.execute("DELETE FROM alert WHERE id = ?", (alert_id,))
    else:
        conn.close()
        return jsonify({"error": "Unsupported action"}), 400

    conn.commit()
    conn.close()
    return jsonify({"message": f"Alert {action}d successfully"})


@alerts_bp.route("/notifications", methods=["GET"])
@login_required
def get_notifications():
    unread_only = request.args.get("unread", "false").lower() == "true"

    conn = get_conn()
    sql = """
        SELECT n.*, a.name AS alert_name
        FROM notification n
        LEFT JOIN alert a ON a.id = n.alert_id
        WHERE n.user_id = ?
    """
    params = [current_user.id]

    if unread_only:
        sql += " AND n.is_read = 0"

    sql += " ORDER BY n.id DESC LIMIT 50"

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])


@alerts_bp.route("/notifications/unread-count", methods=["GET"])
@login_required
def unread_count():
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS unread_count FROM notification WHERE user_id = ? AND is_read = 0",
        (current_user.id,),
    ).fetchone()
    conn.close()
    return jsonify({"unread_count": row["unread_count"]})


@alerts_bp.route("/notifications/<int:notification_id>/read", methods=["PATCH"])
@login_required
def mark_notification_read(notification_id):
    conn = get_conn()
    conn.execute(
        "UPDATE notification SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, current_user.id),
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Notification marked as read"})


@alerts_bp.route("/notifications/clear", methods=["POST"])
@login_required
def clear_notifications():
    conn = get_conn()
    conn.execute("DELETE FROM notification WHERE user_id = ?", (current_user.id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "All notifications cleared"})
