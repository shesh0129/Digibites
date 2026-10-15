# routes/config_api.py — System configuration API blueprint
import json
from flask import Blueprint, jsonify
from db import get_db_connection

config_bp = Blueprint('config_api', __name__, url_prefix='/api')


@config_bp.route('/config', methods=['GET'])
def get_system_config():
    """Returns dynamic categories, canteens, and key-value settings from MySQL."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT code, name, display_order FROM categories ORDER BY display_order ASC")
            categories = cursor.fetchall()

            cursor.execute("SELECT code, name, location FROM canteens ORDER BY id ASC")
            canteens = cursor.fetchall()

            cursor.execute("SELECT config_key, config_value FROM system_config")
            raw_configs = cursor.fetchall()

        config_dict = {}
        for row in raw_configs:
            val = row['config_value']
            try:
                val = json.loads(val)
            except Exception:
                pass
            config_dict[row['config_key']] = val

        return jsonify({
            "success": True,
            "data": {
                "categories": categories,
                "canteens":   canteens,
                "settings":   config_dict,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()
