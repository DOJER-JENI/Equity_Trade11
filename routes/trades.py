from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from models import TradeOrder, db
from services.market_gateway import submit_to_test_market


trades_bp = Blueprint("trades", __name__, url_prefix="/api/trades")


@trades_bp.route("", methods=["POST"])
@login_required
def create_trade():
    data = request.get_json() or {}
    company = str(data.get("company", "")).strip().upper()
    side = str(data.get("side", "")).strip().upper()
    quantity = int(data.get("quantity", 0))
    price = float(data.get("price", 0))
    order_type = str(data.get("order_type", "MARKET")).strip().upper()
    note = str(data.get("note", "")).strip()

    if not company:
        return jsonify({"error": "Company is required"}), 400
    if side not in {"BUY", "SELL"}:
        return jsonify({"error": "Side must be BUY or SELL"}), 400
    if quantity <= 0:
        return jsonify({"error": "Quantity must be greater than 0"}), 400
    if price <= 0:
        return jsonify({"error": "Price must be greater than 0"}), 400

    order = TradeOrder(
        user_id=current_user.id,
        company=company,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
        note=note,
        status="submitted",
    )
    db.session.add(order)
    db.session.commit()
    result = submit_to_test_market(order)
    return jsonify({"message": result["message"], "order_id": order.id, "status": order.status, "market_result": result})


@trades_bp.route("", methods=["GET"])
@login_required
def list_trades():
    orders = TradeOrder.query.filter_by(user_id=current_user.id).order_by(TradeOrder.created_at.desc()).all()
    return jsonify([
        {
            "id": order.id,
            "company": order.company,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "order_type": order.order_type,
            "status": order.status,
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }
        for order in orders
    ])
