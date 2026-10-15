import json
import urllib.request
import urllib.parse
from http.cookiejar import CookieJar

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    cj = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    print("--- 1. Login as Student ---")
    login_data = json.dumps({"username": "student1@gmail.com", "password": "student123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    data = json.loads(res.read().decode('utf-8'))
    print("Login result:", data.get("success"), "| User:", data.get("user", {}).get("full_name"))
    assert data.get("success") is True

    print("\n--- 2. Save Student Allergies (Dairy / Milk & Wheat / Gluten) ---")
    allergy_payload = json.dumps({
        "student_id": "student1@gmail.com",
        "allergies": ["Dairy / Milk", "Wheat / Gluten"]
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/student/allergies", data=allergy_payload, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    save_data = json.loads(res.read().decode('utf-8'))
    print("Save Allergies result:", save_data)
    assert save_data.get("success") is True
    assert "Dairy / Milk" in save_data.get("allergies")

    print("\n--- 3. Verify Allergies from /api/student/allergies ---")
    res = opener.open(f"{BASE_URL}/api/student/allergies?student_id=student1@gmail.com")
    get_data = json.loads(res.read().decode('utf-8'))
    print("Retrieved Allergies:", get_data.get("allergies"))
    assert "Dairy / Milk" in get_data.get("allergies")
    assert "Wheat / Gluten" in get_data.get("allergies")

    print("\n--- 4. Fetch Menu & Check Ingredients and Allergens ---")
    res = opener.open(f"{BASE_URL}/api/menu")
    menu_data = json.loads(res.read().decode('utf-8'))
    items = menu_data.get("data", [])
    print(f"Total Menu Items: {len(items)}")

    # Check Champorado
    champorado = next((i for i in items if i["name"] == "Champorado"), None)
    assert champorado is not None, "Champorado not found"
    print("Champorado Ingredients:", champorado.get("ingredients"))
    print("Champorado Allergens:", champorado.get("allergens"))
    assert "Dairy / Milk" in champorado.get("allergens")

    # Check matching logic:
    student_allergies = set(get_data.get("allergies"))
    matching_items = []
    for item in items:
        item_als = set(item.get("allergens") or [])
        matched = student_allergies.intersection(item_als)
        if matched:
            matching_items.append((item["name"], list(matched)))
    print(f"\nItems triggering automatic allergy warning for student ({len(matching_items)} items):")
    for name, matched in matching_items:
        print(f"  ⚠️ {name}: Contains {matched}")

    assert len(matching_items) > 0, "Expected at least 1 item matching allergies"

    print("\n--- 5. Admin Add / Edit Item with Ingredients & Allergens ---")
    admin_login = json.dumps({"username": "admin", "password": "admin123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=admin_login, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    admin_data = json.loads(res.read().decode('utf-8'))
    print("Admin login result:", admin_data.get("success"), "| Role:", admin_data.get("user", {}).get("role"))

    # Test adding product with ingredients and allergens
    new_product_payload = json.dumps({
        "name": "Test Peanut Butter Toast",
        "price": 30.0,
        "canteen": "JHS",
        "category": "Morning",
        "stock_qty": 25,
        "status": "Available",
        "emoji": "🍞",
        "image_url": "",
        "ingredients": "Toasted white bread, creamy peanut butter, salted butter",
        "allergens": ["Peanuts", "Wheat / Gluten", "Dairy / Milk"]
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/menu", data=new_product_payload, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    new_item_data = json.loads(res.read().decode('utf-8'))
    print("Add Product Result:", new_item_data.get("success"), "| Item ID:", new_item_data.get("item", {}).get("id"))
    assert new_item_data.get("success") is True
    item_id = new_item_data["item"]["id"]

    # Test updating product
    update_payload = json.dumps({
        "name": "Test Peanut Butter Toast",
        "price": 35.0,
        "ingredients": "Toasted whole wheat bread, organic peanut butter, margarine",
        "allergens": ["Peanuts", "Wheat / Gluten"]
    }).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/menu/{item_id}", data=update_payload, headers={"Content-Type": "application/json"})
    req.get_method = lambda: 'PUT'
    res = opener.open(req)
    upd_data = json.loads(res.read().decode('utf-8'))
    print("Update Product Result:", upd_data.get("success"))
    assert upd_data.get("success") is True

    # Delete the test item
    req = urllib.request.Request(f"{BASE_URL}/api/menu/{item_id}")
    req.get_method = lambda: 'DELETE'
    res = opener.open(req)
    del_data = json.loads(res.read().decode('utf-8'))
    print("Cleaned up test item:", del_data.get("success"))

    print("\n✅ ALL ALLERGEN FEATURE TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
