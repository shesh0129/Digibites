import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
import pymysql
from config import Config
from db import get_db_connection

def migrate_allergens():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Check users.allergies
            cursor.execute("SHOW COLUMNS FROM users LIKE 'allergies'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE users ADD COLUMN allergies TEXT AFTER role")
                print("Added 'allergies' column to users.")

            # 2. Check menu_items.image_url
            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'image_url'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN image_url VARCHAR(255) DEFAULT '' AFTER emoji")
                print("Added 'image_url' column to menu_items.")

            # 3. Check menu_items.ingredients
            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'ingredients'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN ingredients TEXT AFTER emoji")
                print("Added 'ingredients' column to menu_items.")

            # 4. Check menu_items.allergens
            cursor.execute("SHOW COLUMNS FROM menu_items LIKE 'allergens'")
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE menu_items ADD COLUMN allergens TEXT AFTER ingredients")
                print("Added 'allergens' column to menu_items.")

            # 5. Populate realistic ingredients and allergens for default menu items
            items_info = [
                {
                    "name": "Champorado",
                    "ingredients": "Glutinous rice, cocoa powder, evaporated milk, cane sugar, water",
                    "allergens": ["Dairy / Milk"]
                },
                {
                    "name": "Sopas",
                    "ingredients": "Elbow macaroni pasta, shredded chicken breast, chicken broth, evaporated milk, carrots, cabbage, butter, garlic, onions",
                    "allergens": ["Dairy / Milk", "Wheat / Gluten", "Eggs"]
                },
                {
                    "name": "Graham Dessert",
                    "ingredients": "Honey graham crackers, sweet condensed milk, all-purpose cream, ripe mangoes",
                    "allergens": ["Dairy / Milk", "Wheat / Gluten"]
                },
                {
                    "name": "Donuts",
                    "ingredients": "Wheat flour, active dry yeast, sugar, fresh whole eggs, cow's milk, butter, chocolate glaze",
                    "allergens": ["Dairy / Milk", "Eggs", "Wheat / Gluten"]
                },
                {
                    "name": "Turon",
                    "ingredients": "Saba bananas, brown sugar, wheat spring roll lumpia wrapper, jackfruit strips, vegetable cooking oil",
                    "allergens": ["Wheat / Gluten"]
                },
                {
                    "name": "Corndog",
                    "ingredients": "Hotdog sausage, yellow cornmeal, wheat flour, egg, fresh milk, panko breadcrumbs, vegetable oil",
                    "allergens": ["Dairy / Milk", "Eggs", "Wheat / Gluten", "Soy"]
                },
                {
                    "name": "Apple Juice",
                    "ingredients": "Filtered water, apple juice concentrate, ascorbic acid (vitamin C), cane sugar",
                    "allergens": []
                },
                {
                    "name": "Hot Chocolate",
                    "ingredients": "Pure cacao tablea, fresh whole milk, dark brown sugar, pinch of sea salt",
                    "allergens": ["Dairy / Milk"]
                },
                {
                    "name": "Chicken Adobo",
                    "ingredients": "Chicken cuts, soy sauce, cane vinegar, garlic, black peppercorns, bay leaves, brown sugar",
                    "allergens": ["Soy", "Wheat / Gluten"]
                },
                {
                    "name": "Pancit Canton",
                    "ingredients": "Egg noodles, pork/chicken slices, soy sauce, oyster sauce, cabbage, carrots, snow peas",
                    "allergens": ["Wheat / Gluten", "Eggs", "Soy", "Shellfish"]
                }
            ]

            for item in items_info:
                cursor.execute("""
                    UPDATE menu_items 
                    SET ingredients = %s, allergens = %s 
                    WHERE name = %s
                """, (item["ingredients"], json.dumps(item["allergens"]), item["name"]))

            # Also set default empty JSON for any remaining items with NULL allergens
            cursor.execute("UPDATE menu_items SET allergens = '[]' WHERE allergens IS NULL OR allergens = ''")
            cursor.execute("UPDATE menu_items SET ingredients = '' WHERE ingredients IS NULL")
            cursor.execute("UPDATE users SET allergies = '[]' WHERE allergies IS NULL OR allergies = ''")

        conn.commit()
        print("Allergen migration completed successfully!")
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_allergens()
