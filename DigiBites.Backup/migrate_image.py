from db import get_db_connection

conn = get_db_connection()
try:
    with conn.cursor() as c:
        c.execute("SHOW COLUMNS FROM menu_items LIKE 'image_url'")
        if not c.fetchone():
            c.execute("ALTER TABLE menu_items ADD COLUMN image_url VARCHAR(500) DEFAULT '' AFTER emoji")
            print("Added image_url column")
        else:
            print("image_url column already exists")
    conn.commit()
finally:
    conn.close()
