import json
import pymysql
from pymysql.cursors import DictCursor
from werkzeug.security import generate_password_hash
from config import Config

def get_db_connection():
    """Returns a new MySQL connection with DictCursor for dictionary-like row access."""
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=DictCursor,
        autocommit=False
    )

def init_db():
    """Initializes tables, ensures columns exist, and seeds defaults for a fully configurable POS & Ordering system."""
    # Ensure database exists
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    with conn.cursor() as cursor:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}`")
    conn.commit()
    conn.close()

    # Connect to the database
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Users table (Admin & Customer roles)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(100) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'customer',
                    phone_number VARCHAR(20) NULL,
                    grade_level VARCHAR(20) NULL,
                    section VARCHAR(100) NULL,
                    lrn VARCHAR(12) NULL,
                    student_id_filename VARCHAR(255) NULL,
                    verification_status VARCHAR(20) NOT NULL DEFAULT 'approved',
                    verification_note TEXT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            user_columns = {
                'phone_number': "ALTER TABLE users ADD COLUMN phone_number VARCHAR(20) NULL AFTER role",
                'grade_level': "ALTER TABLE users ADD COLUMN grade_level VARCHAR(20) NULL AFTER phone_number",
                'section': "ALTER TABLE users ADD COLUMN section VARCHAR(100) NULL AFTER grade_level",
                'lrn': "ALTER TABLE users ADD COLUMN lrn VARCHAR(12) NULL AFTER role",
                'student_id_filename': "ALTER TABLE users ADD COLUMN student_id_filename VARCHAR(255) NULL AFTER lrn",
                'verification_status': "ALTER TABLE users ADD COLUMN verification_status VARCHAR(20) NOT NULL DEFAULT 'approved' AFTER student_id_filename",
                'verification_note': "ALTER TABLE users ADD COLUMN verification_note TEXT NULL AFTER verification_status",
            }
            for column, alter_sql in user_columns.items():
                cursor.execute("SHOW COLUMNS FROM users LIKE %s", (column,))
                if not cursor.fetchone():
                    cursor.execute(alter_sql)

            cursor.execute("SHOW INDEX FROM users WHERE Key_name = 'uq_users_lrn'")
            if not cursor.fetchone():
                cursor.execute("CREATE UNIQUE INDEX uq_users_lrn ON users (lrn)")

            # 2. Categories table (Configurable categories)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    display_order INT DEFAULT 0
                )
            """)

            # 3. Canteens table (Configurable canteens/locations)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS canteens (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    location VARCHAR(100) DEFAULT ''
                )
            """)

            # 4. Products / Menu items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS menu_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    price DECIMAL(10, 2) NOT NULL,
                    canteen VARCHAR(50) NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    stock_qty INT NOT NULL DEFAULT 50,
                    status VARCHAR(50) NOT NULL DEFAULT 'Available',
                    emoji VARCHAR(10) DEFAULT '🍲',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'canteen'")
            if not cursor.fetchone():
                cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'canteen_location'")
                has_canteen_location = cursor.fetchone() is not None
                cursor.execute(
                    "ALTER TABLE menu_items ADD COLUMN canteen VARCHAR(50) NOT NULL DEFAULT 'SHS' AFTER price"
                )
                if has_canteen_location:
                    cursor.execute("""
                        UPDATE menu_items
                        SET canteen = UPPER(TRIM(canteen_location))
                        WHERE canteen_location IS NOT NULL AND TRIM(canteen_location) != ''
                    """)

            # Ensure allergies and last_active_at column in users
            cursor.execute("SHOW COLUMNS FROM users LIKE 'allergies'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN allergies TEXT AFTER role")

            cursor.execute("SHOW COLUMNS FROM users LIKE 'last_active_at'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN last_active_at TIMESTAMP NULL AFTER verification_note")

            # Add stock_qty or emoji column if menu_items already existed without them
            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'stock_qty'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN stock_qty INT NOT NULL DEFAULT 50 AFTER category")
            
            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'emoji'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN emoji VARCHAR(10) DEFAULT '🍲' AFTER status")

            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'image_url'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN image_url VARCHAR(255) DEFAULT '' AFTER emoji")

            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'ingredients'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN ingredients TEXT AFTER emoji")

            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'allergens'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN allergens TEXT AFTER ingredients")

            # Normalize existing assignments to the two supported canteen codes.
            cursor.execute("""
                UPDATE menu_items
                SET canteen = CASE
                    WHEN UPPER(TRIM(canteen)) IN ('JHS', 'JHS CANTEEN', 'JUNIOR HIGH SCHOOL', 'JUNIOR HIGH SCHOOL CANTEEN')
                        THEN 'JHS'
                    ELSE 'SHS'
                END
            """)

            # Daily Income Log Table for financial reset snapshots & audits
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_income_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    log_date DATE NOT NULL,
                    total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
                    paid_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,
                    total_orders INT NOT NULL DEFAULT 0,
                    reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reset_by VARCHAR(100) DEFAULT '',
                    notes TEXT NULL
                )
            """)

            # 5. Orders table (with payment and tracking details)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_number VARCHAR(30) UNIQUE NOT NULL,
                    student_id VARCHAR(50) NOT NULL,
                    customer_name VARCHAR(100) NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL,
                    total DECIMAL(10, 2) NOT NULL,
                    payment_method VARCHAR(50) NOT NULL DEFAULT 'Cash on Pickup',
                    payment_status VARCHAR(50) NOT NULL DEFAULT 'Unpaid',
                    status VARCHAR(50) NOT NULL DEFAULT 'Waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add missing columns to orders if table previously existed
            cursor.execute("SHOW COLUMNS FROM orders LIKE 'order_number'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE orders ADD COLUMN order_number VARCHAR(30) DEFAULT '' AFTER id")
                # Populate existing rows with an order number
                cursor.execute("UPDATE orders SET order_number = CONCAT('ORD-', id) WHERE order_number = '' OR order_number IS NULL")

            cursor.execute("SHOW COLUMNS FROM orders LIKE 'customer_name'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE orders ADD COLUMN customer_name VARCHAR(100) DEFAULT '' AFTER student_id")

            cursor.execute("SHOW COLUMNS FROM orders LIKE 'payment_method'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE orders ADD COLUMN payment_method VARCHAR(50) DEFAULT 'Cash on Pickup' AFTER total")

            cursor.execute("SHOW COLUMNS FROM orders LIKE 'payment_status'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'Unpaid' AFTER payment_method")

            # 6. System Configuration table (Key-Value store for zero hardcoding)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    config_key VARCHAR(50) PRIMARY KEY,
                    config_value TEXT NOT NULL
                )
            """)

            # Seed system_config
            default_configs = [
                ("canteen_name", "DigiBites Digital Canteen"),
                ("canteen_tagline", "Smart School POS & Pre-Ordering"),
                ("currency_symbol", "₱"),
                ("order_statuses", json.dumps(["Waiting", "Processing", "To Pickup", "Completed", "Cancelled"])),
                ("payment_methods", json.dumps(["Cash on Pickup", "GCash", "Campus Card"]))
            ]
            for key, val in default_configs:
                cursor.execute("""
                    INSERT INTO system_config (config_key, config_value)
                    VALUES (%s, %s)
                    ON DUPLICATE KEY UPDATE config_value = VALUES(config_value)
                """, (key, val))

            # Seed categories
            cursor.execute("SELECT COUNT(*) AS count FROM categories")
            if cursor.fetchone()['count'] == 0:
                default_categories = [
                    ("Morning", "Morning (Breakfast)", 1),
                    ("Afternoon", "Afternoon (Lunch)", 2),
                    ("Snacks", "Snacks & Desserts", 3),
                    ("Beverages", "Drinks & Beverages", 4)
                ]
                cursor.executemany("""
                    INSERT INTO categories (code, name, display_order)
                    VALUES (%s, %s, %s)
                """, default_categories)

            # Seed canteens
            cursor.execute("SELECT COUNT(*) AS count FROM canteens")
            if cursor.fetchone()['count'] == 0:
                default_canteens = [
                    ("JHS", "JHS Canteen", "Building A - Ground Floor"),
                    ("SHS", "SHS Canteen", "Building B - 2nd Floor")
                ]
                cursor.executemany("""
                    INSERT INTO canteens (code, name, location)
                    VALUES (%s, %s, %s)
                """, default_canteens)

            # Seed users (Admin and Customer)
            cursor.execute("SELECT COUNT(*) AS count FROM users")
            if cursor.fetchone()['count'] == 0:
                admin_pw = generate_password_hash("admin123")
                student_pw = generate_password_hash("student123")
                initial_users = [
                    ("admin", admin_pw, "Canteen Staff Admin", "admin"),
                    ("student1@gmail.com", student_pw, "Juan Dela Cruz", "customer")
                ]
                cursor.executemany("""
                    INSERT INTO users (username, password_hash, full_name, role)
                    VALUES (%s, %s, %s, %s)
                """, initial_users)
                print("Seeded default users (admin: admin123, student1@gmail.com: student123).")

            # Ensure standard initial menu items exist
            initial_menu = [
                ("Champorado", 25.00, "JHS", "Morning", 35, "Available", "🍲"),
                ("Sopas", 25.00, "SHS", "Morning", 30, "Available", "🥣"),
                ("Graham Dessert", 20.00, "JHS", "Morning", 20, "Available", "🍰"),
                ("Donuts", 10.00, "SHS", "Morning", 40, "Available", "🍩"),
                ("Turon", 15.00, "JHS", "Afternoon", 25, "Available", "🍌"),
                ("Corndog", 20.00, "SHS", "Afternoon", 0, "Sold Out", "🌭"),
                ("Apple Juice", 15.00, "SHS", "Beverages", 45, "Available", "🧃"),
                ("Hot Chocolate", 20.00, "JHS", "Beverages", 30, "Available", "☕")
            ]
            for item in initial_menu:
                cursor.execute("SELECT id FROM menu_items WHERE name = %s AND canteen = %s", (item[0], item[2]))
                if not cursor.fetchone():
                    cursor.execute("""
                        INSERT INTO menu_items (name, price, canteen, category, stock_qty, status, emoji)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, item)


        conn.commit()
        print("Database schema verified and ready for POS & Ordering System.")
    finally:
        conn.close()

if __name__ == '__main__':
    init_db()
