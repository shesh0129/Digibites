# routes/pages.py — Server-side page routes with auth guards
from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for

pages_bp = Blueprint('pages', __name__)


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('pages.login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('pages.login_page'))
        if session.get('role') not in ('admin', 'staff'):
            return redirect(url_for('pages.customer_dashboard'))
        return f(*args, **kwargs)
    return decorated


def customer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('pages.login_page'))
        if session.get('role') != 'customer':
            return redirect(url_for('pages.admin_dashboard'))
        return f(*args, **kwargs)
    return decorated


def _user():
    """Build user dict from session for template context."""
    val = session.get('email') or session.get('username') or ''
    return {
        'id': session.get('user_id'),
        'username': val,
        'email': val,
        'full_name': session.get('full_name') or 'User',
        'role': session.get('role'),
    }


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@pages_bp.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('pages.admin_dashboard'))
        return redirect(url_for('pages.customer_dashboard'))
    return redirect(url_for('pages.login_page'))


@pages_bp.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('pages.index'))
    return render_template('auth/login.html')


# ---------------------------------------------------------------------------
# Customer routes
# ---------------------------------------------------------------------------

@pages_bp.route('/customer/dashboard')
@customer_required
def customer_dashboard():
    return render_template('customer/dashboard.html', user=_user())


@pages_bp.route('/customer/menu')
@customer_required
def customer_menu():
    return render_template('customer/menu.html', user=_user())


@pages_bp.route('/customer/cart')
@customer_required
def customer_cart():
    return render_template('customer/cart.html', user=_user())


@pages_bp.route('/customer/orders')
@customer_required
def customer_orders():
    return render_template('customer/orders.html', user=_user())


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@pages_bp.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin/dashboard.html', user=_user())


@pages_bp.route('/admin/pos')
@admin_required
def admin_pos():
    return render_template('admin/pos.html', user=_user())


@pages_bp.route('/admin/orders')
@admin_required
def admin_orders():
    return render_template('admin/orders.html', user=_user())


@pages_bp.route('/admin/inventory')
@admin_required
def admin_inventory():
    return render_template('admin/inventory.html', user=_user())


@pages_bp.route('/admin/student-verifications')
@admin_required
def admin_student_verifications():
    return render_template('admin/student_verifications.html', user=_user())


@pages_bp.route('/admin/users')
@admin_required
def admin_users():
    return render_template('admin/users.html', user=_user())


# ---------------------------------------------------------------------------
# Convenience Aliases / Short Redirects
# ---------------------------------------------------------------------------

@pages_bp.route('/pos')
def alias_pos():
    return redirect(url_for('pages.admin_pos'))


@pages_bp.route('/inventory')
def alias_inventory():
    return redirect(url_for('pages.admin_inventory'))


@pages_bp.route('/dashboard')
def alias_dashboard():
    return redirect(url_for('pages.index'))


@pages_bp.route('/menu')
def alias_menu():
    return redirect(url_for('pages.customer_menu'))


@pages_bp.route('/cart')
def alias_cart():
    return redirect(url_for('pages.customer_cart'))


@pages_bp.route('/orders')
def alias_orders():
    if session.get('role') == 'admin':
        return redirect(url_for('pages.admin_orders'))
    return redirect(url_for('pages.customer_orders'))


@pages_bp.route('/admin')
def alias_admin():
    return redirect(url_for('pages.admin_dashboard'))


@pages_bp.route('/customer')
def alias_customer():
    return redirect(url_for('pages.customer_dashboard'))

