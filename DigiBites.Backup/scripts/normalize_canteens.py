import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from config import Config

conn = pymysql.connect(
    host=Config.DB_HOST,
    port=Config.DB_PORT,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME
)
with conn.cursor() as cur:
    cur.execute("UPDATE menu_items SET category = 'Snacks' WHERE category = '' OR category = 'ADD-ONS'")
    cur.execute("UPDATE menu_items SET category = 'Afternoon' WHERE category = 'MISTER TAKOYAKI'")
    cur.execute("UPDATE menu_items SET category = 'Beverages' WHERE category LIKE '%TEA%'")
    cur.execute("UPDATE menu_items SET canteen = 'JHS' WHERE name IN ('Graham Dessert', 'Turon', 'Hot Chocolate', 'Champorado')")
    
    jhs_extras = [
        ('Chicken Arroz Caldo', 30.00, 'JHS', 'Morning', 35, 'Available', '🥣', 'Chicken, rice, ginger, scallions', '[]'),
        ('Pork Adobo with Rice', 50.00, 'JHS', 'Afternoon', 40, 'Available', '🍛', 'Pork, soy sauce, vinegar, garlic, rice', '["Soy"]'),
        ('Mango Juice', 15.00, 'JHS', 'Beverages', 45, 'Available', '🧃', 'Mango fruit extract, water, sugar', '[]'),
        ('Banana Cue', 15.00, 'JHS', 'Snacks', 30, 'Available', '🍌', 'Saba banana, brown sugar, cooking oil', '[]')
    ]
    for name, price, canteen, cat, qty, status, emoji, ingr, aller in jhs_extras:
        cur.execute('SELECT id FROM menu_items WHERE name = %s AND canteen = %s', (name, canteen))
        if not cur.fetchone():
            cur.execute(
                'INSERT INTO menu_items (name, price, canteen, category, stock_qty, status, emoji, ingredients, allergens) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (name, price, canteen, cat, qty, status, emoji, ingr, aller)
            )
conn.commit()
conn.close()
print('Menu items successfully normalized and balanced for JHS and SHS.')
