import json
from datetime import datetime

from models import AppSetting, TradeOrder, db


def get_setting(key: str, default: str = "") -> str:
    item = AppSetting.query.filter_by(key=key).first()
    return item.value if item and item.value is not None else default


def submit_to_test_market(order: TradeOrder) -> dict:
    enabled = get_setting("TEST_MARKET_ENABLED", "false").lower() == "true"
    provider = get_setting("TEST_MARKET_PROVIDER", "PaperTrade")

    if not enabled:
        order.status = "rejected"
        order.market_response = json.dumps({"message": "Test market disabled"})
        db.session.commit()
        return {"ok": False, "message": "Test market connectivity is disabled in admin settings."}

    simulated = {
        "provider": provider,
        "reference_id": f"SIM-{order.company}-{order.id}",
        "executed_at": datetime.utcnow().isoformat(),
        "status": "accepted",
    }
    order.status = "accepted"
    order.market_response = json.dumps(simulated)
    db.session.commit()
    return {"ok": True, "message": "Order submitted to test market successfully.", "data": simulated}
