# DigiBites - Configurable POS & Ordering System

A configurable Point-of-Sale (POS) and Pre-Ordering System built with **Flask**, **MySQL**, and modern Vanilla HTML/CSS/JS.

---

## 1. System Roles

The system supports two primary roles with dedicated interfaces:

| Role | Username / Password | Capabilities |
|---|---|---|
| **Admin (Staff)** | `admin` / `admin123` | • Live Kitchen / POS Queue management<br>• Real-time order progress updates (`Waiting`, `Processing`, `To Pickup`, `Completed`, `Cancelled`)<br>• Mark orders as Paid / Unpaid<br>• Product & Inventory Management (Add items, edit stock, toggle Available / Sold Out, Delete)<br>• Live daily revenue and queue analytics |
| **Customer (Student)** | `student1` / `student123`<br>*(or submit a student application via Sign Up)* | • Apply with name, Gmail, Philippine phone, 12-digit LRN, grade, section, and current school ID image<br>• Sign in after staff approve the application<br>• Browse dynamic menu by Category and Canteen<br>• Basket & Pre-Order checkout with Payment Method selection<br>• Live order progress tracking and order history |

Self-registration validates the LRN format and mobile number, but does not connect to a DepEd or school registry. Staff must compare the submitted details and ID against official school records in **Student Verification** before approving access. ID images are stored outside `static/`, downloadable only by admins, and deleted after a decision. Pending applications retain their image until reviewed.

---

## 2. Zero Hardcoding Architecture

All business logic, product data, categories, canteens, statuses, and payment methods are dynamically retrieved from the MySQL database:

- **`users` Table:** Stores customer and staff accounts with hashed passwords (`werkzeug.security`).
- **`categories` Table:** Configurable menu categories (e.g. `Morning`, `Afternoon`, `Snacks`, `Beverages`).
- **`canteens` Table:** Configurable locations / branches (e.g. `JHS Canteen`, `SHS Canteen`).
- **`menu_items` Table:** Catalog with a `canteen` assignment (`SHS` or `JHS`), real-time stock quantities (`stock_qty`), pricing, and statuses (`Available`, `Sold Out`). Customer browsing and checkout stay within one selected canteen per order; staff can filter and assign inventory by canteen.
- **`orders` Table:** Live order records with unique readable order numbers (e.g. `ORD-3819-21`), payment method, payment status, and order status.
- **`system_config` Table:** Key-value configuration for payment options, order statuses, and branding.

---

## 3. Quick Start Guide

### Start MySQL Database (Docker)
```powershell
docker compose up -d
```
*(Or if the container exists: `docker start digibites-mysql`)*

### Install Dependencies
```powershell
pip install -r requirements.txt
```

### Configure the Session Secret
Set a persistent random `SECRET_KEY` in the ignored `.env` file before deployment. Generate one with:
```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```
The application uses a random development-only fallback when the known sample key is configured; that fallback changes on restart, so deployments must provide their own stable secret.

### Initialize / Migrate Database
```powershell
python db.py
```

### Run Application
```powershell
python app.py
```
Open **http://localhost:5000** in your browser.

---

## 4. API Endpoints

### Authentication
- `POST /api/auth/register` — Submit a student application with LRN and school ID image
- `POST /api/auth/login` — Sign in as customer or admin
- `GET /api/auth/admin/student-verifications` — *(Admin)* List pending applications
- `GET /api/auth/admin/student-verifications/<id>/document` — *(Admin)* Download pending school ID evidence
- `POST /api/auth/admin/student-verifications/<id>/review` — *(Admin)* Approve or reject an application
- `GET /api/auth/admin/users` — *(Admin)* List staff accounts
- `POST /api/auth/admin/users` — *(Admin)* Create a staff administrator account
- `PUT /api/auth/admin/users/<id>` — *(Admin)* Update staff name, Gmail, or password
- `DELETE /api/auth/admin/users/<id>` — *(Admin)* Delete a staff account (cannot delete self or the last administrator)

### Configuration & Catalog
- `GET /api/config` — Fetch categories, canteens, and dynamic system settings
- `GET /api/menu` — Fetch catalog items (supports `?category=...&canteen=...`)
- `POST /api/menu` — *(Admin)* Add new product
- `PUT /api/menu/<id>` — *(Admin)* Update price, stock, or status
- `DELETE /api/menu/<id>` — *(Admin)* Remove product

### Orders & POS
- `GET /api/orders` — Fetch customer or admin order queue
- `POST /api/orders` — Place order and decrement inventory
- `PUT /api/orders/<id>/status` — *(Admin)* Update order status or payment status
- `GET /api/admin/stats` — *(Admin)* Get active queue count and sales summary
