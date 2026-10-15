# routes/orders.py — Orders API blueprint
import json
import random
import time
from flask import Blueprint, request, jsonify, session
from db import get_db_connection

orders_bp = Blueprint('orders', __name__, url_prefix='/api/orders')


@orders_bp.route('', methods=['GET'])
def get_orders():
    """Fetch orders for the authenticated customer or administrator."""
    role = session.get('role')
    if 'user_id' not in session or role not in {'admin', 'customer'}:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    view = request.args.get('view', '').strip().lower()  # 'active', 'completed', or ''
    canteen = request.args.get('canteen', '').strip()

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if role == 'admin':
                base_query = (
                    "SELECT o.*, u.id AS profile_user_id, u.username AS profile_email, "
                    "u.full_name AS profile_full_name, u.phone_number AS profile_phone, "
                    "u.grade_level AS profile_grade, u.section AS profile_section, "
                    "u.lrn AS profile_lrn, u.verification_status AS profile_verification_status "
                    "FROM orders o LEFT JOIN users u ON u.username = o.student_id "
                )
                conditions = []
                params = []

                if view == 'active':
                    # Active FIFO queue: exclude completed & paid orders
                    conditions.append("o.status IN ('Waiting', 'Processing', 'To Pickup') AND NOT (o.status = 'Completed' AND o.payment_status = 'Paid')")
                    order_by = " ORDER BY o.id ASC"  # FIFO: Oldest order first
                elif view == 'completed':
                    conditions.append("(o.status = 'Completed' OR o.payment_status = 'Paid')")
                    order_by = " ORDER BY o.id DESC"
                else:
                    order_by = " ORDER BY o.id DESC"

                where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
                cursor.execute(base_query + where_clause + order_by, tuple(params))
            else:
                student_id = session.get('username') or session.get('email')
                cursor.execute("SELECT * FROM orders WHERE student_id = %s ORDER BY id DESC", (student_id,))
            orders = cursor.fetchall()

        def _fmt(idx, o):
            try:
                items = json.loads(o["items_json"]) if isinstance(o["items_json"], str) else o["items_json"]
            except Exception:
                items = []
            formatted = {
                "order_id":       o["id"],
                "queue_pos":      idx + 1 if view == 'active' else None,
                "order_number":   o.get("order_number") or f"ORD-{o['id']}",
                "student_id":     o["student_id"],
                "customer_name":  o.get("customer_name") or o["student_id"],
                "items":          items,
                "total":          float(o["total"]),
                "payment_method": o.get("payment_method", "Cash on Pickup"),
                "payment_status": o.get("payment_status", "Unpaid"),
                "status":         o["status"],
                "created_at":     o["created_at"].strftime('%Y-%m-%d %H:%M') if o.get("created_at") else None,
            }
            if role == 'admin':
                formatted['student_profile'] = {
                    "full_name": o.get('profile_full_name'),
                    "email": o.get('profile_email'),
                    "phone": o.get('profile_phone'),
                    "grade": o.get('profile_grade'),
                    "section": o.get('profile_section'),
                    "lrn": o.get('profile_lrn'),
                    "verification_status": o.get('profile_verification_status'),
                } if o.get('profile_user_id') else None
            return formatted

        return jsonify({"success": True, "data": [_fmt(i, o) for i, o in enumerate(orders)]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@orders_bp.route('/live-queue', methods=['GET'])
def get_live_queue():
    """Real-time FIFO active queue synchronization endpoint for staff terminals."""
    if session.get('role') not in ('admin', 'staff'):
        return jsonify({"success": False, "message": "Staff or administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Fetch only active, unpaid/uncompleted orders in FIFO order (created_at / id ASC)
            cursor.execute("""
                SELECT o.*, u.id AS profile_user_id, u.username AS profile_email,
                       u.full_name AS profile_full_name, u.phone_number AS profile_phone,
                       u.grade_level AS profile_grade, u.section AS profile_section,
                       u.lrn AS profile_lrn, u.verification_status AS profile_verification_status
                FROM orders o
                LEFT JOIN users u ON u.username = o.student_id
                WHERE o.status IN ('Waiting', 'Processing', 'To Pickup')
                  AND NOT (o.status = 'Completed' AND o.payment_status = 'Paid')
                ORDER BY o.id ASC
            """)
            orders = cursor.fetchall()

            waiting_cnt = sum(1 for o in orders if o.get('status') == 'Waiting')
            processing_cnt = sum(1 for o in orders if o.get('status') == 'Processing')
            ready_cnt = sum(1 for o in orders if o.get('status') == 'To Pickup')

        formatted = []
        for idx, o in enumerate(orders):
            try:
                items = json.loads(o["items_json"]) if isinstance(o["items_json"], str) else o["items_json"]
            except Exception:
                items = []

            formatted.append({
                "queue_pos":      idx + 1,  # Dynamic FIFO position (#1, #2, #3...)
                "order_id":       o["id"],
                "order_number":   o.get("order_number") or f"ORD-{o['id']}",
                "student_id":     o["student_id"],
                "customer_name":  o.get("customer_name") or o["student_id"],
                "items":          items,
                "total":          float(o["total"]),
                "payment_method": o.get("payment_method", "Cash on Pickup"),
                "payment_status": o.get("payment_status", "Unpaid"),
                "status":         o["status"],
                "created_at":     o["created_at"].strftime('%Y-%m-%d %H:%M') if o.get("created_at") else "",
                "created_time":   o["created_at"].strftime('%H:%M') if o.get("created_at") else "",
                "student_profile": {
                    "full_name": o.get('profile_full_name'),
                    "email": o.get('profile_email'),
                    "phone": o.get('profile_phone'),
                    "grade": o.get('profile_grade'),
                    "section": o.get('profile_section'),
                    "lrn": o.get('profile_lrn'),
                    "verification_status": o.get('profile_verification_status'),
                } if o.get('profile_user_id') else None
            })

        return jsonify({
            "success":          True,
            "total_active":     len(formatted),
            "waiting_count":    waiting_cnt,
            "processing_count": processing_cnt,
            "ready_count":      ready_cnt,
            "queue":            formatted,
            "timestamp":        time.time()
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@orders_bp.route('', methods=['POST'])
def place_order():
    """Place a customer pre-order or an administrator/staff POS order."""
    data = request.get_json(silent=True)
    role = session.get('role')
    if 'user_id' not in session or role not in {'admin', 'customer', 'staff'}:
        return jsonify({"success": False, "message": "Authentication required."}), 401
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Invalid order data."}), 400

    items = data.get("items", [])

    if not isinstance(items, list) or not items:
        return jsonify({"success": False, "message": "No items provided."}), 400

    selected_canteen = None
    if role == 'customer':
        selected_canteen = str(
            data.get('canteen_location') or data.get('canteen') or ''
        ).strip().upper()
        if selected_canteen not in ('SHS', 'JHS'):
            return jsonify({
                "success": False,
                "message": "Select either the SHS or JHS canteen before placing an order.",
            }), 400

    quantities = []
    for item in items:
        if not isinstance(item, dict):
            return jsonify({"success": False, "message": "Invalid order item."}), 400
        raw_quantity = item.get('qty', 1)
        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            return jsonify({"success": False, "message": "Item quantities must be whole numbers."}), 422
        if isinstance(raw_quantity, float) and not raw_quantity.is_integer():
            return jsonify({"success": False, "message": "Item quantities must be whole numbers."}), 422
        if quantity < 1:
            return jsonify({"success": False, "message": "Each item quantity must be at least one."}), 422
        quantities.append(quantity)

    if role == 'customer':
        student_id = session.get('username') or session.get('email')
        customer_name = session.get('full_name') or student_id
    else:
        student_id = data.get("student_id", "Guest")
        customer_name = data.get("customer_name", student_id)
    payment_method = data.get("payment_method", "Cash on Pickup")
    payment_status = 'Unpaid' if role == 'customer' else data.get('payment_status', 'Unpaid')
    order_number   = f"ORD-{int(time.time() % 10000):04d}-{random.randint(10, 99)}"

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if role == 'customer':
                quantities_by_item = {}
                for item, quantity in zip(items, quantities):
                    item_id = item.get('id')
                    if item_id is None:
                        return jsonify({"success": False, "message": "A menu item is missing its ID."}), 422
                    cursor.execute(
                        "SELECT id, name, canteen, price, stock_qty, status FROM menu_items WHERE id = %s",
                        (item_id,)
                    )
                    menu_item = cursor.fetchone()
                    if not menu_item:
                        return jsonify({"success": False, "message": "A menu item is no longer available."}), 422
                    if menu_item['canteen'] != selected_canteen:
                        return jsonify({
                            "success": False,
                            "message": f"{menu_item['name']} belongs to the {menu_item['canteen']} canteen, not {selected_canteen}.",
                        }), 422
                    canonical_id = menu_item['id']
                    quantities_by_item[canonical_id] = quantities_by_item.get(canonical_id, 0) + quantity
                    if quantities_by_item[canonical_id] > 2:
                        return jsonify({
                            "success": False,
                            "code": "item_quantity_limit",
                            "message": f"Maximum 2 pieces of {menu_item['name']} per student order.",
                        }), 422
                    if menu_item['status'] != 'Available' or menu_item['stock_qty'] < quantities_by_item[canonical_id]:
                        return jsonify({
                            "success": False,
                            "message": f"{menu_item['name']} is no longer available in the requested quantity.",
                        }), 422
                    item['id'] = canonical_id
                    item['name'] = menu_item['name']
                    item['price'] = float(menu_item['price'])
                    item['canteen'] = selected_canteen

            total = sum(item.get("price", 0) * quantity for item, quantity in zip(items, quantities))
            items_json = json.dumps(items)
            cursor.execute(
                "INSERT INTO orders (order_number, student_id, customer_name, items_json, total, payment_method, payment_status, status) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,'Waiting')",
                (order_number, student_id, customer_name, items_json, total, payment_method, payment_status)
            )
            order_id = cursor.lastrowid

            # Deduct stock
            for itm in items:
                if itm.get('id') is not None:
                    cursor.execute(
                        "UPDATE menu_items SET stock_qty = GREATEST(0, stock_qty - %s), "
                        "status = IF(stock_qty - %s <= 0, 'Sold Out', status) WHERE id = %s",
                        (itm.get('qty', 1), itm.get('qty', 1), itm['id'])
                    )
                else:
                    cursor.execute(
                        "UPDATE menu_items SET stock_qty = GREATEST(0, stock_qty - %s), "
                        "status = IF(stock_qty - %s <= 0, 'Sold Out', status) WHERE name = %s",
                        (itm.get('qty', 1), itm.get('qty', 1), itm.get('name'))
                    )
        conn.commit()

        return jsonify({
            "success": True,
            "message": "Order placed successfully!",
            "order":   {
                "order_id":       order_id,
                "order_number":   order_number,
                "student_id":     student_id,
                "customer_name":  customer_name,
                "items":          items,
                "total":          float(total),
                "payment_method": payment_method,
                "payment_status": payment_status,
                "status":         "Waiting",
                **({"canteen": selected_canteen} if selected_canteen else {}),
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@orders_bp.route('/<int:order_id>/status', methods=['PUT'])
def update_order_status(order_id):
    """Admin/Staff: update order status and/or payment status."""
    if session.get('role') not in ('admin', 'staff'):
        return jsonify({"success": False, "message": "Staff or administrator access required."}), 403
    data           = request.get_json(silent=True) or {}
    new_status     = data.get("status")
    payment_status = data.get("payment_status")

    if not new_status and not payment_status:
        return jsonify({"success": False, "message": "No status updates provided."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if new_status and payment_status:
                cursor.execute("UPDATE orders SET status=%s, payment_status=%s WHERE id=%s",
                               (new_status, payment_status, order_id))
            elif new_status:
                cursor.execute("UPDATE orders SET status=%s WHERE id=%s", (new_status, order_id))
            else:
                cursor.execute("UPDATE orders SET payment_status=%s WHERE id=%s", (payment_status, order_id))
        conn.commit()
        return jsonify({"success": True, "message": f"Order #{order_id} updated."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
