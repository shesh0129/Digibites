# routes/menu.py — Menu / Products API blueprint
import json
import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, session
from db import get_db_connection
from validators import ValidationHelper

menu_bp = Blueprint('menu', __name__, url_prefix='/api/menu')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def _parse_json_list(val):
    if not val:
        return []
    if isinstance(val, list):
        return val
    try:
        res = json.loads(val)
        return res if isinstance(res, list) else []
    except Exception:
        return []


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _require_staff():
    if session.get('role') not in ('admin', 'staff'):
        return jsonify({"success": False, "message": "Staff or administrator access required."}), 403
    return None


@menu_bp.route('/upload-image', methods=['POST'])
def upload_menu_image():
    """Upload a food product image and return its public URL."""
    denied = _require_staff()
    if denied:
        return denied

    if 'image' not in request.files and 'file' not in request.files:
        return jsonify({"success": False, "message": "No image file provided."}), 400

    file = request.files.get('image') or request.files.get('file')
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "No file selected."}), 400

    if not allowed_file(file.filename):
        return jsonify({"success": False, "message": "Invalid file format. Allowed: PNG, JPG, JPEG, WEBP, GIF."}), 400

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"food_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
    dest_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(dest_path)

    image_url = f"/static/uploads/{unique_name}"
    return jsonify({
        "success": True,
        "message": "Image uploaded successfully.",
        "image_url": image_url
    })


@menu_bp.route('', methods=['GET'])
def get_menu():
    """Fetch all menu items. Filterable by ?canteen= or ?canteen_location= and ?category="""
    canteen  = request.args.get('canteen') or request.args.get('canteen_location')
    category = request.args.get('category')
    if canteen:
        canteen = canteen.strip().upper()
        if canteen not in ('SHS', 'JHS', 'ALL'):
            return jsonify({"success": False, "message": "Canteen must be SHS, JHS, or ALL."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            query  = "SELECT * FROM menu_items WHERE 1=1"
            params = []
            if canteen and canteen.upper() != 'ALL':
                query += " AND canteen = %s"
                params.append(canteen)
            if category and category.lower() != 'all':
                query += " AND category = %s"
                params.append(category)
            query += " ORDER BY id ASC"
            cursor.execute(query, tuple(params))
            items = cursor.fetchall()

        return jsonify({
            "success": True,
            "data": [
                {
                    "id":               item["id"],
                    "name":             item["name"],
                    "price":            float(item["price"]),
                    "canteen":          item["canteen"],
                    "canteen_location": item["canteen"],
                    "category":         item["category"],
                    "stock_qty":        item.get("stock_qty", 50),
                    "status":           item["status"],
                    "emoji":            item.get("emoji", "🍲"),
                    "image_url":        item.get("image_url") or "",
                    "ingredients":      item.get("ingredients") or "",
                    "allergens":        _parse_json_list(item.get("allergens")),
                }
                for item in items
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@menu_bp.route('', methods=['POST'])
def add_menu_item():
    """Admin: add a new product with ingredients and allergen profile."""
    denied = _require_staff()
    if denied:
        return denied

    data        = request.get_json(silent=True) or {}
    name        = ValidationHelper.normalize_string(data.get('name', ''))
    price       = data.get('price', 0)
    canteen     = (data.get('canteen_location') or data.get('canteen', 'SHS'))
    canteen     = str(canteen).strip().upper()
    if canteen not in ('SHS', 'JHS'):
        return jsonify({"success": False, "message": "Canteen must be SHS or JHS."}), 400
    category    = data.get('category', 'Morning')
    stock_qty   = int(data.get('stock_qty', 50))
    status      = data.get('status', 'Available')
    emoji       = data.get('emoji', '🍲')
    image_url   = (data.get('image_url') or '').strip()
    ingredients = (data.get('ingredients') or '').strip()
    
    allergens_raw = data.get('allergens', [])
    if isinstance(allergens_raw, list):
        allergens_str = json.dumps(allergens_raw)
    elif isinstance(allergens_raw, str):
        allergens_str = allergens_raw
    else:
        allergens_str = '[]'

    if not name or float(price) <= 0:
        return jsonify({"success": False, "message": "Valid item name and price are required."}), 400

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO menu_items (name, price, canteen, category, stock_qty, status, emoji, image_url, ingredients, allergens) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name, price, canteen, category, stock_qty, status, emoji, image_url, ingredients, allergens_str)
            )
            item_id = cursor.lastrowid
        conn.commit()
        return jsonify({
            "success": True,
            "message": f"Product '{name}' added.",
            "item": {
                "id":               item_id,
                "name":             name,
                "price":            float(price),
                "canteen":          canteen,
                "canteen_location": canteen,
                "category":         category,
                "stock_qty":        stock_qty,
                "status":           status,
                "emoji":            emoji,
                "image_url":        image_url,
                "ingredients":      ingredients,
                "allergens":        _parse_json_list(allergens_str)
            }
        }), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@menu_bp.route('/<int:item_id>', methods=['PUT'])
def update_menu_item(item_id):
    """Admin: update an existing product with ingredients and allergens."""
    denied = _require_staff()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM menu_items WHERE id = %s", (item_id,))
            existing = cursor.fetchone()
            if not existing:
                return jsonify({"success": False, "message": "Product not found."}), 404

            name      = data.get('name',      existing['name'])
            price     = data.get('price',     existing['price'])
            canteen   = data.get('canteen_location', data.get('canteen', existing['canteen']))
            canteen   = str(canteen).strip().upper()
            if canteen not in ('SHS', 'JHS'):
                return jsonify({"success": False, "message": "Canteen must be SHS or JHS."}), 400
            category  = data.get('category',  existing['category'])
            stock_qty = data.get('stock_qty', existing.get('stock_qty', 50))
            status    = data.get('status',    existing['status'])
            emoji     = data.get('emoji',     existing.get('emoji', '🍲'))
            image_url = data.get('image_url', existing.get('image_url') or '')
            if image_url is not None:
                image_url = str(image_url).strip()

            ingredients = data.get('ingredients', existing.get('ingredients') or '')
            if ingredients is not None:
                ingredients = str(ingredients).strip()

            if 'allergens' in data:
                allergens_raw = data.get('allergens')
                if isinstance(allergens_raw, list):
                    allergens_str = json.dumps(allergens_raw)
                elif isinstance(allergens_raw, str):
                    allergens_str = allergens_raw
                else:
                    allergens_str = '[]'
            else:
                allergens_str = existing.get('allergens') or '[]'

            cursor.execute(
                "UPDATE menu_items SET name=%s, price=%s, canteen=%s, category=%s, stock_qty=%s, status=%s, emoji=%s, image_url=%s, ingredients=%s, allergens=%s WHERE id=%s",
                (name, price, canteen, category, stock_qty, status, emoji, image_url, ingredients, allergens_str, item_id)
            )
        conn.commit()
        return jsonify({"success": True, "message": "Product updated."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@menu_bp.route('/<int:item_id>', methods=['DELETE'])
def delete_menu_item(item_id):
    """Admin: remove a product."""
    denied = _require_staff()
    if denied:
        return denied

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM menu_items WHERE id = %s", (item_id,))
        conn.commit()
        return jsonify({"success": True, "message": "Product removed."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()


@menu_bp.route('/<int:item_id>/restock', methods=['POST'])
def restock_menu_item(item_id):
    """Admin: quick +N stock restock."""
    denied = _require_staff()
    if denied:
        return denied

    data   = request.get_json(silent=True) or {}
    amount = int(data.get('amount', 10))
    conn   = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE menu_items SET stock_qty = stock_qty + %s, status = 'Available' WHERE id = %s",
                (amount, item_id)
            )
        conn.commit()
        return jsonify({"success": True, "message": f"Added {amount} units to stock."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
