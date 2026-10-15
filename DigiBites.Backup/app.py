# app.py — DigiBites Flask Application Factory
from flask import Flask
from flask_cors import CORS
from config import Config
from db import init_db
from routes.pages      import pages_bp
from routes.auth       import auth_bp
from routes.menu       import menu_bp
from routes.orders     import orders_bp
from routes.stats      import stats_bp
from routes.config_api import config_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)

    # Register blueprints
    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(config_bp)

    @app.before_request
    def track_user_activity():
        from flask import session, request
        import time
        from db import get_db_connection
        if 'user_id' in session:
            # Throttle DB updates to once every 60 seconds
            now = time.time()
            last_ping = session.get('_last_active_ping', 0)
            if now - last_ping > 60:
                session['_last_active_ping'] = now
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cursor:
                        cursor.execute("UPDATE users SET last_active_at = CURRENT_TIMESTAMP WHERE id = %s", (session['user_id'],))
                    conn.commit()
                    conn.close()
                except Exception:
                    pass

    # Initialize DB on first run
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            print(f"Warning: Could not auto-initialize database: {e}")

    return app


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)