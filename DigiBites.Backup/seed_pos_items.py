from db import get_db_connection

items_data = [
    ("Aglio Olio", 145.00, "Main Canteen", "MISTER TAKOYAKI", 22, "Available", "🍝", "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=500&q=80"),
    ("Americano", 89.00, "Main Canteen", "COFFEE", 211, "Available", "☕", "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=500&q=80"),
    ("Egg Add-on", 20.00, "Main Canteen", "ADD-ONS", 318, "Available", "🍳", "https://images.unsplash.com/photo-1582722872445-44dc5f7e3c8f?w=500&q=80"),
    ("Barista's Choice", 145.00, "Main Canteen", "COFFEE", 211, "Available", "🧋", "https://images.unsplash.com/photo-1577968897966-3d4325b36b61?w=500&q=80"),
    ("Beef Cheese Nachos", 175.00, "Main Canteen", "ADD-ONS", 9, "Available", "🧀", "https://images.unsplash.com/photo-1513456852971-30c0b8199d4d?w=500&q=80"),
    ("Beef Lasagna", 169.00, "Main Canteen", "MISTER TAKOYAKI", 13, "Available", "🥘", "https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=500&q=80"),
    ("Beef Pepper Garlic", 169.00, "Main Canteen", "MISTER TAKOYAKI", 44, "Available", "🥩", "https://images.unsplash.com/photo-1544025162-d76694265947?w=500&q=80"),
    ("Berry Choco", 120.00, "Main Canteen", "NON COFFEE", 1898, "Available", "🍫", "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=500&q=80"),
    ("Biscoff Latte", 160.00, "Main Canteen", "COFFEE", 38, "Available", "☕", "https://images.unsplash.com/photo-1541167760496-1628856ab772?w=500&q=80"),
    ("Biscoff Oat", 145.00, "Main Canteen", "NON COFFEE", 48, "Available", "🥛", "https://images.unsplash.com/photo-1568651316527-302a9eb786f0?w=500&q=80"),
    ("Blueberry Special", 70.00, "Main Canteen", "MATCHA SERIES", 31, "Available", "🫐", "https://images.unsplash.com/photo-1553530666-ba11a7da3888?w=500&q=80"),
    ("Bottled Water", 20.00, "Main Canteen", "NON COFFEE", 125, "Available", "💧", "https://images.unsplash.com/photo-1548839140-29a749e1bc4e?w=500&q=80"),
    ("Crispy Chicken Wings", 189.00, "Main Canteen", "CHICKEN WINGS", 45, "Available", "🍗", "https://images.unsplash.com/photo-1567620832903-9fc6debc209f?w=500&q=80"),
    ("Classic Takoyaki", 120.00, "Main Canteen", "MISTER TAKOYAKI", 50, "Available", "🐙", "https://images.unsplash.com/photo-1615361200141-f45040f367be?w=500&q=80"),
    ("Matcha Latte", 135.00, "Main Canteen", "MATCHA SERIES", 42, "Available", "🍵", "https://images.unsplash.com/photo-1536256263959-770b48d82b0a?w=500&q=80"),
    ("Twinning's Earl Grey", 95.00, "Main Canteen", "TWINNING'S TEA", 35, "Available", "🫖", "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=500&q=80"),
]

conn = get_db_connection()
try:
    with conn.cursor() as c:
        for item in items_data:
            c.execute("SELECT id FROM menu_items WHERE name = %s", (item[0],))
            exist = c.fetchone()
            if exist:
                c.execute("""
                    UPDATE menu_items 
                    SET price = %s, canteen = %s, category = %s, stock_qty = %s, status = %s, emoji = %s, image_url = %s
                    WHERE id = %s
                """, (item[1], item[2], item[3], item[4], item[5], item[6], item[7], exist['id']))
            else:
                c.execute("""
                    INSERT INTO menu_items (name, price, canteen, category, stock_qty, status, emoji, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, item)
        # Also ensure original items have good fallback images
        c.execute("UPDATE menu_items SET image_url = 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=500&q=80' WHERE (image_url IS NULL OR image_url = '') AND name = 'Champorado'")
        c.execute("UPDATE menu_items SET image_url = 'https://images.unsplash.com/photo-1547592166-23ac45744acd?w=500&q=80' WHERE (image_url IS NULL OR image_url = '') AND name = 'Sopas'")
        c.execute("UPDATE menu_items SET image_url = 'https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=500&q=80' WHERE (image_url IS NULL OR image_url = '') AND name = 'Donuts'")
        c.execute("UPDATE menu_items SET image_url = 'https://images.unsplash.com/photo-1627054234032-4752b04f323c?w=500&q=80' WHERE (image_url IS NULL OR image_url = '') AND name = 'Corndog'")
    conn.commit()
    print("Successfully seeded POS items with images!")
finally:
    conn.close()
