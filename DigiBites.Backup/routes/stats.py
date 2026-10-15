# routes/stats.py — Dashboard stats API blueprint
import json
from datetime import date as dt_date, datetime
# pyrefly: ignore [missing-import]
from flask import Blueprint, current_app, request, jsonify, session
from db import get_db_connection

stats_bp = Blueprint('stats', __name__, url_prefix='/api')


@stats_bp.route('/admin/stats', methods=['GET'])
def admin_stats():
    """Comprehensive KPI data for the Staff Dashboard."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total_orders, COALESCE(SUM(total),0) AS total_revenue FROM orders")
            orders_stat = cursor.fetchone()

            cursor.execute("""
                SELECT
                    SUM(IF(status='Waiting',1,0))                              AS waiting_count,
                    SUM(IF(status='Processing',1,0))                           AS processing_count,
                    SUM(IF(status='To Pickup',1,0))                            AS ready_count,
                    SUM(IF(status='Completed',1,0))                            AS completed_count,
                    SUM(IF(status IN ('Waiting','Processing','To Pickup'),1,0)) AS active_count
                FROM orders
            """)
            breakdown = cursor.fetchone()

            cursor.execute("""
                SELECT id, name, canteen, category, stock_qty, status, emoji, price
                FROM menu_items WHERE stock_qty <= 10 OR status = 'Sold Out'
                ORDER BY stock_qty ASC
            """)
            low_stock_items = [
                {"id": i["id"], "name": i["name"], "canteen": i["canteen"],
                 "category": i["category"], "stock_qty": i["stock_qty"],
                 "status": i["status"], "emoji": i.get("emoji", "🍲"),
                 "price": float(i["price"])}
                for i in cursor.fetchall()
            ]

            cursor.execute("""
                SELECT id, order_number, customer_name, items_json, total,
                       payment_method, payment_status, status, created_at
                FROM orders
                WHERE status IN ('Waiting','Processing','To Pickup')
                ORDER BY id DESC LIMIT 5
            """)
            recent_queue = []
            for r in cursor.fetchall():
                try:
                    items = json.loads(r["items_json"]) if isinstance(r["items_json"], str) else r["items_json"]
                except Exception:
                    items = []
                recent_queue.append({
                    "order_id":       r["id"],
                    "order_number":   r["order_number"] or f"ORD-{r['id']}",
                    "customer_name":  r["customer_name"],
                    "items":          items,
                    "total":          float(r["total"]),
                    "payment_method": r["payment_method"],
                    "payment_status": r["payment_status"],
                    "status":         r["status"],
                    "created_at":     r["created_at"].strftime('%H:%M') if r.get("created_at") else "",
                })

        return jsonify({
            "success": True,
            "data": {
                "total_orders":      orders_stat['total_orders'] or 0,
                "total_revenue":     float(orders_stat['total_revenue'] or 0),
                "active_orders":     breakdown['active_count'] or 0,
                "waiting_count":     breakdown['waiting_count'] or 0,
                "processing_count":  breakdown['processing_count'] or 0,
                "ready_count":       breakdown['ready_count'] or 0,
                "completed_count":   breakdown['completed_count'] or 0,
                "low_stock_count":   len(low_stock_items),
                "low_stock_items":   low_stock_items,
                "recent_queue":      recent_queue,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@stats_bp.route('/admin/daily-report', methods=['GET'])
def admin_daily_report():
    """Summarized report: sum of profit for the day & tomorrow's restock/prep list."""
    from datetime import date as dt_date, datetime
    target_date_str = request.args.get('date')
    if not target_date_str:
        target_date_str = dt_date.today().strftime('%Y-%m-%d')

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Check if today was reset
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'daily_income_reset_at'")
            row_reset_at = cursor.fetchone()
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'daily_income_reset_date'")
            row_reset_date = cursor.fetchone()
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'daily_income_reset_order_id'")
            row_reset_order_id = cursor.fetchone()

            is_reset_today = False
            reset_at_str = None
            reset_order_id = None
            if row_reset_date and row_reset_date.get('config_value') == target_date_str and row_reset_at:
                reset_at_str = row_reset_at.get('config_value')
                is_reset_today = True
                if row_reset_order_id:
                    try:
                        reset_order_id = int(row_reset_order_id.get('config_value'))
                    except (TypeError, ValueError):
                        reset_order_id = None

            cursor.execute("SELECT * FROM daily_income_log WHERE log_date = %s ORDER BY id DESC LIMIT 1", (target_date_str,))
            archived_today_row = cursor.fetchone()

            if is_reset_today and reset_order_id is not None:
                cursor.execute("""
                    SELECT id, order_number, customer_name, items_json, total,
                           payment_method, payment_status, status, created_at
                    FROM orders
                    WHERE DATE(created_at) = %s AND id > %s
                    ORDER BY id DESC
                """, (target_date_str, reset_order_id))
                today_orders_rows = cursor.fetchall()
            elif is_reset_today and reset_at_str:
                cursor.execute("""
                    SELECT id, order_number, customer_name, items_json, total,
                           payment_method, payment_status, status, created_at
                    FROM orders
                    WHERE DATE(created_at) = %s AND created_at > %s
                    ORDER BY id DESC
                """, (target_date_str, reset_at_str))
                today_orders_rows = cursor.fetchall()
            else:
                cursor.execute("""
                    SELECT id, order_number, customer_name, items_json, total,
                           payment_method, payment_status, status, created_at
                    FROM orders
                    WHERE DATE(created_at) = %s
                    ORDER BY id DESC
                """, (target_date_str,))
                today_orders_rows = cursor.fetchall()

            # If today has 0 orders, also check if there are recent orders on another day to show benchmark
            # BUT ONLY if today was NOT reset! If it was reset, we must show 0.00!
            is_fallback_date = False
            if not today_orders_rows and not request.args.get('date') and not is_reset_today:
                cursor.execute("SELECT MAX(DATE(created_at)) AS latest_date FROM orders")
                latest_row = cursor.fetchone()
                if latest_row and latest_row.get('latest_date'):
                    latest_date_str = latest_row['latest_date'].strftime('%Y-%m-%d')
                    if latest_date_str != target_date_str:
                        cursor.execute("""
                            SELECT id, order_number, customer_name, items_json, total,
                                   payment_method, payment_status, status, created_at
                            FROM orders
                            WHERE DATE(created_at) = %s
                            ORDER BY id DESC
                        """, (latest_date_str,))
                        today_orders_rows = cursor.fetchall()
                        target_date_str = latest_date_str
                        is_fallback_date = True

            # 2. Fetch all menu items
            cursor.execute("""
                SELECT id, name, canteen, category, price, stock_qty, status, emoji
                FROM menu_items
                ORDER BY category, name
            """)
            all_menu_items = cursor.fetchall()

        # Parse item consumption today
        item_sales_map = {}  # {item_name: {"qty": X, "revenue": Y, "emoji": ...}}
        total_revenue = 0.0
        paid_revenue  = 0.0
        unpaid_revenue = 0.0
        payment_methods = {"Cash on Pickup": {"count": 0, "total": 0.0},
                           "GCash": {"count": 0, "total": 0.0},
                           "Maya": {"count": 0, "total": 0.0}}
        order_status_counts = {"Waiting": 0, "Processing": 0, "To Pickup": 0, "Completed": 0, "Cancelled": 0}

        for ord_row in today_orders_rows:
            ord_total = float(ord_row.get("total") or 0)
            total_revenue += ord_total
            if ord_row.get("payment_status") == "Paid":
                paid_revenue += ord_total
            else:
                unpaid_revenue += ord_total

            pm = ord_row.get("payment_method") or "Cash on Pickup"
            if pm not in payment_methods:
                payment_methods[pm] = {"count": 0, "total": 0.0}
            payment_methods[pm]["count"] += 1
            payment_methods[pm]["total"] += ord_total

            st = ord_row.get("status") or "Waiting"
            order_status_counts[st] = order_status_counts.get(st, 0) + 1

            # Parse items JSON
            raw_items = ord_row.get("items_json") or "[]"
            try:
                items_list = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
            except Exception:
                items_list = []

            for itm in items_list:
                name = itm.get("name")
                qty = int(itm.get("qty") or 1)
                price = float(itm.get("price") or 0)
                emoji = itm.get("emoji") or "🍲"
                if name not in item_sales_map:
                    item_sales_map[name] = {"qty": 0, "revenue": 0.0, "emoji": emoji, "unit_price": price}
                item_sales_map[name]["qty"] += qty
                item_sales_map[name]["revenue"] += (price * qty)

        # Calculate estimated Food Cost & Net Profit (60% standard food cost ratio = 40% gross profit margin)
        # In canteen management, standard gross margin benchmark is 40%
        estimated_cost = round(total_revenue * 0.60, 2)
        estimated_profit = round(total_revenue - estimated_cost, 2)
        profit_margin_pct = round((estimated_profit / total_revenue * 100), 1) if total_revenue > 0 else 0.0

        # Top selling items today
        top_selling = sorted(
            [{"name": k, "qty": v["qty"], "revenue": v["revenue"], "emoji": v["emoji"]}
             for k, v in item_sales_map.items()],
            key=lambda x: x["qty"],
            reverse=True
        )[:5]

        # 3. Calculate Tomorrow's Stock-In & Prep Recommendations
        # An item needs restocking if:
        # - stock_qty <= 15 OR status = 'Sold Out' OR sold_today >= stock_qty
        tomorrow_restock_list = []
        total_units_to_prep = 0
        est_total_prep_cost = 0.0

        for mi in all_menu_items:
            m_id = mi["id"]
            name = mi["name"]
            canteen = mi["canteen"]
            category = mi["category"]
            price = float(mi["price"])
            stock_qty = int(mi.get("stock_qty") or 0)
            status = mi["status"]
            emoji = mi.get("emoji") or "🍲"

            sold_today = item_sales_map.get(name, {}).get("qty", 0)

            # Restock logic: target at least 40 servings or 1.5x of today's sales
            target_stock = max(40, int(sold_today * 1.5))
            needed_stock = target_stock - stock_qty

            needs_restock = (
                stock_qty <= 15 or 
                status == 'Sold Out' or 
                (sold_today >= 8 and stock_qty <= 20)
            )

            if needs_restock and needed_stock > 0:
                # Determine urgency
                if stock_qty <= 0 or status == 'Sold Out':
                    urgency = 'Critical (Out of Stock)'
                    urgency_level = 1
                elif stock_qty <= 8:
                    urgency = 'High (Critically Low)'
                    urgency_level = 2
                elif sold_today >= 10:
                    urgency = 'High Velocity (High Demand)'
                    urgency_level = 2
                else:
                    urgency = 'Moderate Restock'
                    urgency_level = 3

                unit_cost = round(price * 0.60, 2)
                item_prep_cost = round(unit_cost * needed_stock, 2)

                tomorrow_restock_list.append({
                    "id": m_id,
                    "name": name,
                    "emoji": emoji,
                    "canteen": canteen,
                    "category": category,
                    "price": price,
                    "current_stock": stock_qty,
                    "sold_today": sold_today,
                    "target_stock": target_stock,
                    "recommended_stock_in": needed_stock,
                    "status": status,
                    "urgency": urgency,
                    "urgency_level": urgency_level,
                    "unit_cost": unit_cost,
                    "est_prep_cost": item_prep_cost,
                })

                total_units_to_prep += needed_stock
                est_total_prep_cost += item_prep_cost

        # Sort restock list by urgency first, then by recommended qty
        tomorrow_restock_list.sort(key=lambda x: (x["urgency_level"], -x["recommended_stock_in"]))

        return jsonify({
            "success": True,
            "data": {
                "report_date": target_date_str,
                "is_fallback_date": is_fallback_date,
                "today_orders": len(today_orders_rows),
                "today_revenue": round(total_revenue, 2),
                "today_cost": estimated_cost,
                "today_profit": estimated_profit,
                "profit_margin_pct": profit_margin_pct,
                "paid_revenue": round(paid_revenue, 2),
                "unpaid_revenue": round(unpaid_revenue, 2),
                "avg_order_value": round(total_revenue / len(today_orders_rows), 2) if today_orders_rows else 0.0,
                "payment_methods": payment_methods,
                "order_status_counts": order_status_counts,
                "is_reset_today": is_reset_today,
                "reset_at": reset_at_str,
                "archived_today": {
                    "total_revenue": float(archived_today_row['total_revenue']) if archived_today_row else 0.0,
                    "paid_revenue": float(archived_today_row['paid_revenue']) if archived_today_row else 0.0,
                    "total_orders": int(archived_today_row['total_orders']) if archived_today_row else 0,
                    "reset_at": archived_today_row['reset_at'].strftime('%H:%M') if (archived_today_row and archived_today_row.get('reset_at')) else '',
                } if archived_today_row else None,
                "tomorrow_restock_list": tomorrow_restock_list,
                "total_items_to_restock": len(tomorrow_restock_list),
                "total_units_to_prep": total_units_to_prep,
                "est_total_prep_cost": round(est_total_prep_cost, 2),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@stats_bp.route('/admin/quick-restock', methods=['POST'])
def admin_quick_restock():
    """Quickly stock-in an item or batch of items from tomorrow's prep list."""
    data = request.get_json(silent=True) or {}
    item_id = data.get('item_id')
    add_qty = int(data.get('add_qty', 0))
    batch   = data.get('batch', [])

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            if batch:
                for b in batch:
                    b_id = b.get('id')
                    b_qty = int(b.get('qty', 0))
                    if b_id and b_qty > 0:
                        cursor.execute("""
                            UPDATE menu_items 
                            SET stock_qty = stock_qty + %s, status = 'Available'
                            WHERE id = %s
                        """, (b_qty, b_id))
            elif item_id and add_qty > 0:
                cursor.execute("""
                    UPDATE menu_items 
                    SET stock_qty = stock_qty + %s, status = 'Available'
                    WHERE id = %s
                """, (add_qty, item_id))
            else:
                return jsonify({"success": False, "message": "Invalid item or quantity."}), 400

        conn.commit()
        return jsonify({"success": True, "message": "Stock updated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()



@stats_bp.route('/student/stats', methods=['GET'])
def student_stats():
    """Personalized stats for the Customer Dashboard."""
    student_id = request.args.get('student_id')
    if not student_id:
        return jsonify({"success": False, "message": "student_id is required"}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS total_orders,
                       COALESCE(SUM(total),0) AS total_spent,
                       SUM(IF(status IN ('Waiting','Processing','To Pickup'),1,0)) AS active_orders
                FROM orders WHERE student_id = %s
            """, (student_id,))
            stat = cursor.fetchone()

        return jsonify({
            "success": True,
            "data": {
                "total_orders":  stat['total_orders'] or 0,
                "total_spent":   float(stat['total_spent'] or 0),
                "active_orders": stat['active_orders'] or 0,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@stats_bp.route('/student/allergies', methods=['GET', 'POST'])
def student_allergies():
    """Get or update student allergy preferences."""
    # pyrefly: ignore [missing-import]
    from flask import session
    conn = get_db_connection()
    try:
        if request.method == 'GET':
            student_id = request.args.get('student_id') or session.get('username') or session.get('email')
            if not student_id:
                return jsonify({"success": False, "message": "student_id or active session required"}), 400

            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT allergies FROM users WHERE username = %s OR id = %s LIMIT 1",
                    (student_id, student_id if str(student_id).isdigit() else -1)
                )
                row = cursor.fetchone()
                if not row:
                    return jsonify({"success": True, "allergies": []})

                raw = row.get('allergies') or '[]'
                try:
                    allergies = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
                except Exception:
                    allergies = []

            return jsonify({"success": True, "allergies": allergies})

        elif request.method == 'POST':
            data = request.get_json(silent=True) or {}
            student_id = data.get('student_id') or session.get('username') or session.get('email')
            if not student_id:
                return jsonify({"success": False, "message": "student_id or active session required"}), 400

            allergies_in = data.get('allergies', [])
            if not isinstance(allergies_in, list):
                allergies_in = []

            allergies_str = json.dumps(allergies_in)

            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE users SET allergies = %s WHERE username = %s OR id = %s",
                    (allergies_str, student_id, student_id if str(student_id).isdigit() else -1)
                )
            conn.commit()

            # Sync session if logged in
            session['allergies'] = allergies_in

            return jsonify({
                "success": True,
                "allergies": allergies_in,
                "message": "Allergy preferences saved successfully."
            })
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Feature 2 — Daily Income Reset
# ---------------------------------------------------------------------------

@stats_bp.route('/admin/reset-daily-income', methods=['POST'])
def reset_daily_income():
    """Admin: Archive today's income snapshot then zero the daily counter."""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    today = dt_date.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Lock the reset date so two simultaneous closings cannot archive the same interval.
            cursor.execute("""
                INSERT INTO system_config (config_key, config_value)
                VALUES ('daily_income_reset_date', %s)
                ON DUPLICATE KEY UPDATE config_value = config_value
            """, (today,))
            cursor.execute(
                "SELECT config_value FROM system_config "
                "WHERE config_key = 'daily_income_reset_date' FOR UPDATE"
            )
            row_prev_date = cursor.fetchone()
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'daily_income_reset_at'")
            row_prev_reset = cursor.fetchone()
            cursor.execute("SELECT config_value FROM system_config WHERE config_key = 'daily_income_reset_order_id'")
            row_prev_order_id = cursor.fetchone()

            prev_reset_time = None
            prev_order_id = None
            if row_prev_date and row_prev_date.get('config_value') == today:
                prev_reset_time = row_prev_reset.get('config_value') if row_prev_reset else None
                if row_prev_order_id:
                    try:
                        prev_order_id = int(row_prev_order_id.get('config_value'))
                    except (TypeError, ValueError):
                        prev_order_id = None

            # Archive the closed interval and its order-id boundary in the same transaction.
            if prev_order_id is not None:
                cursor.execute("""
                    SELECT
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(total), 0)                               AS total_revenue,
                        COALESCE(SUM(IF(payment_status='Paid', total, 0)), 0) AS paid_revenue,
                        MAX(id) AS last_order_id
                    FROM orders
                    WHERE DATE(created_at) = %s AND id > %s
                """, (today, prev_order_id))
            elif prev_reset_time:
                cursor.execute("""
                    SELECT
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(total), 0)                               AS total_revenue,
                        COALESCE(SUM(IF(payment_status='Paid', total, 0)), 0) AS paid_revenue,
                        MAX(id) AS last_order_id
                    FROM orders
                    WHERE DATE(created_at) = %s AND created_at > %s
                """, (today, prev_reset_time))
            else:
                cursor.execute("""
                    SELECT
                        COUNT(*) AS total_orders,
                        COALESCE(SUM(total), 0)                               AS total_revenue,
                        COALESCE(SUM(IF(payment_status='Paid', total, 0)), 0) AS paid_revenue,
                        MAX(id) AS last_order_id
                    FROM orders
                    WHERE DATE(created_at) = %s
                """, (today,))
            summary = cursor.fetchone()

            total_revenue = float(summary['total_revenue'] or 0)
            paid_revenue  = float(summary['paid_revenue']  or 0)
            total_orders  = int(summary['total_orders']    or 0)
            reset_order_id = summary['last_order_id'] or prev_order_id
            if reset_order_id is None and prev_reset_time:
                cursor.execute("""
                    SELECT COALESCE(MAX(id), 0) AS last_order_id
                    FROM orders
                    WHERE DATE(created_at) = %s AND created_at <= %s
                """, (today, prev_reset_time))
                reset_order_id = cursor.fetchone()['last_order_id']
            reset_order_id = reset_order_id or 0

            # Archive the snapshot
            reset_by = session.get('full_name') or session.get('username') or 'Admin'
            cursor.execute("""
                INSERT INTO daily_income_log
                    (log_date, total_revenue, paid_revenue, total_orders, reset_by, notes)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (today, total_revenue, paid_revenue, total_orders, reset_by, f"Daily closing reset by {reset_by}"))

            # Record reset date so the dashboard knows today was reset
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            for k, v in [('daily_income_reset_date', today),
                         ('daily_income_reset_at', now_str),
                         ('daily_income_reset_order_id', str(reset_order_id))]:
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                """, (k, v))

        conn.commit()
        return jsonify({
            "success": True,
            "message": f"Daily income for {today} has been successfully reset to ₱0.00 and archived.",
            "archived": {
                "date":          today,
                "total_revenue": total_revenue,
                "paid_revenue":  paid_revenue,
                "total_orders":  total_orders,
                "reset_by":      reset_by,
                "reset_at":      now_str,
            }
        })
    except Exception:
        conn.rollback()
        current_app.logger.exception("Could not archive and reset daily income")
        return jsonify({"success": False, "message": "Could not reset daily income. No changes were saved."}), 503
    finally:
        conn.close()


@stats_bp.route('/admin/daily-income-history', methods=['GET'])
def daily_income_history():
    """Admin: Return list of archived daily reset logs."""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_income_log (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    log_date      DATE NOT NULL,
                    total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
                    paid_revenue  DECIMAL(10,2) NOT NULL DEFAULT 0,
                    total_orders  INT NOT NULL DEFAULT 0,
                    reset_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reset_by      VARCHAR(100) DEFAULT '',
                    notes         TEXT NULL
                )
            """)
            cursor.execute("SELECT * FROM daily_income_log ORDER BY id DESC LIMIT 50")
            rows = cursor.fetchall()

        logs = [
            {
                "id":            r["id"],
                "log_date":      r["log_date"].strftime('%Y-%m-%d') if r.get("log_date") else "",
                "total_revenue": float(r["total_revenue"] or 0),
                "paid_revenue":  float(r["paid_revenue"] or 0),
                "total_orders":  int(r["total_orders"] or 0),
                "reset_at":      r["reset_at"].strftime('%Y-%m-%d %H:%M:%S') if r.get("reset_at") else "",
                "reset_by":      r.get("reset_by") or "Admin",
                "notes":         r.get("notes") or "",
            }
            for r in rows
        ]
        return jsonify({"success": True, "data": logs})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Feature 4 — Non-Admin Account Analytics & Directory
# ---------------------------------------------------------------------------

@stats_bp.route('/admin/customer-users', methods=['GET'])
def list_customer_users():
    """Admin: List all non-admin (student/customer) accounts with metrics."""
    if session.get('role') != 'admin':
        return jsonify({"success": False, "message": "Administrator access required."}), 403

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, username, full_name, phone_number,
                       grade_level, section, lrn,
                       verification_status, created_at, last_active_at
                FROM users
                WHERE role = 'customer'
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()

            # Approved accounts
            cursor.execute("""
                SELECT COUNT(*) AS active_count
                FROM users
                WHERE role = 'customer' AND verification_status = 'approved'
            """)
            active_count = int((cursor.fetchone() or {}).get('active_count', 0))

            # Recently active online users
            cursor.execute("""
                SELECT COUNT(*) AS online_count
                FROM users
                WHERE role = 'customer' AND last_active_at >= NOW() - INTERVAL 60 MINUTE
            """)
            online_count = int((cursor.fetchone() or {}).get('online_count', 0))
            if online_count == 0 and active_count > 0:
                online_count = active_count

            # Pending accounts
            cursor.execute("""
                SELECT COUNT(*) AS pending_count
                FROM users
                WHERE role = 'customer' AND verification_status = 'pending'
            """)
            pending_count = int((cursor.fetchone() or {}).get('pending_count', 0))

            # Staff accounts
            cursor.execute("SELECT COUNT(*) AS staff_count FROM users WHERE role = 'admin'")
            staff_count = int((cursor.fetchone() or {}).get('staff_count', 0))

        data = [
            {
                "id":          r['id'],
                "username":    r['username'],
                "email":       r['username'],
                "full_name":   r['full_name'] or '',
                "phone":       r['phone_number'] or '',
                "grade":       r['grade_level'] or '',
                "section":     r['section'] or '',
                "lrn":         r['lrn'] or '',
                "status":      r['verification_status'] or 'approved',
                "created_at":  r['created_at'].strftime('%Y-%m-%d') if r.get('created_at') else '',
                "last_active": r['last_active_at'].strftime('%Y-%m-%d %H:%M') if r.get('last_active_at') else 'Recently',
            }
            for r in rows
        ]

        return jsonify({
            "success":       True,
            "total_users":   len(data),
            "active_count":  active_count,
            "online_count":  online_count,
            "pending_count": pending_count,
            "staff_count":   staff_count,
            "data":          data,
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
