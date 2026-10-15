// DigiBites - Configurable POS & Ordering System
// State Management & Client Logic

let currentUser = null; // { id, username, full_name, role }
let cart = [];
let menuItems = [];
let systemConfig = {
    categories: [],
    canteens: [],
    settings: {}
};
let customerOrders = [];
let allAdminOrders = [];
let adminStatsData = null;
let currentCategoryFilter = 'all';
let currentAdminOrderFilter = 'All';

// -------------------------------------------------------------
// 1. INITIALIZATION & AUTHENTICATION
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
    // Check local storage for persistent session
    const savedUser = localStorage.getItem('digibites_user');
    if (savedUser) {
        try {
            currentUser = JSON.parse(savedUser);
        } catch (e) {
            currentUser = null;
        }
    }

    // Load dynamic configuration and catalog
    await loadSystemConfig();
    await loadMenu();

    if (currentUser) {
        setupUserInterface(currentUser);
    } else {
        switchTab('login');
    }
});

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.toggle('active');
    if (overlay) overlay.classList.toggle('hidden');
}

function switchAuthMode(mode) {
    const tabSignin = document.getElementById('tab-btn-signin');
    const tabSignup = document.getElementById('tab-btn-signup');
    const formLogin = document.getElementById('login-form');
    const formRegister = document.getElementById('register-form');
    const subtext = document.getElementById('auth-subtext');

    if (mode === 'signin') {
        tabSignin.classList.add('active');
        tabSignup.classList.remove('active');
        formLogin.classList.remove('hidden');
        formRegister.classList.add('hidden');
        if (subtext) subtext.innerText = 'Canteen POS & Pre-Ordering Portal';
    } else {
        tabSignup.classList.add('active');
        tabSignin.classList.remove('active');
        formRegister.classList.remove('hidden');
        formLogin.classList.add('hidden');
        if (subtext) subtext.innerText = 'Create a Customer Account to Pre-Order Food';
    }
}

function fillDemo(identifier, password) {
    switchAuthMode('signin');
    const userIn = document.getElementById('login-email') || document.getElementById('login-username');
    const passIn = document.getElementById('login-password');
    if (userIn) userIn.value = identifier;
    if (passIn) passIn.value = password;
    showToast(`Loaded ${identifier} credentials.`);
}

async function handleLogin(event) {
    if (event) event.preventDefault();
    const emailEl = document.getElementById('login-email') || document.getElementById('login-username');
    const email = emailEl ? emailEl.value.trim() : '';
    const password = document.getElementById('login-password').value;

    if (!email || !password) {
        showToast('Please enter both email and password.');
        return;
    }

    if (email.toLowerCase() !== 'admin' && !/^[a-zA-Z0-9._%+-]+@gmail\.com$/i.test(email)) {
        showToast('Only @gmail.com email addresses are accepted.');
        return;
    }

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        const result = await response.json();

        if (response.ok && result.success) {
            currentUser = result.user;
            localStorage.setItem('digibites_user', JSON.stringify(currentUser));
            setupUserInterface(currentUser);
            showToast(result.message || `Welcome, ${currentUser.full_name}!`);
        } else {
            showToast(result.message || 'Login failed. Please check credentials.');
        }
    } catch (err) {
        showToast('Server connection error during login.');
    }
}

async function handleRegister(event) {
    if (event) event.preventDefault();
    const fullName = document.getElementById('reg-fullname').value.trim();
    const emailEl = document.getElementById('reg-email') || document.getElementById('reg-username');
    const email = emailEl ? emailEl.value.trim() : '';
    const password = document.getElementById('reg-password').value;
    const confirmPassword = (document.getElementById('reg-confirm') || document.getElementById('reg-confirm-password') || {}).value;

    if (!fullName || !email || !password) {
        showToast('Please fill in all registration fields.');
        return;
    }

    if (!/^[a-zA-Z0-9._%+-]+@gmail\.com$/i.test(email)) {
        showToast('Only @gmail.com email addresses are accepted.');
        return;
    }

    if (password !== confirmPassword) {
        showToast('Passwords do not match.');
        return;
    }

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ full_name: fullName, email, password })
        });
        const result = await response.json();

        if (response.ok && result.success) {
            showToast('Account created successfully! Please sign in.');
            switchAuthMode('signin');
            const userIn = document.getElementById('login-email') || document.getElementById('login-username');
            const passIn = document.getElementById('login-password');
            if (userIn) userIn.value = email;
            if (passIn) passIn.value = password;
        } else {
            showToast(result.message || 'Registration failed.');
        }
    } catch (err) {
        showToast('Server error during registration.');
    }
}

function logout() {
    currentUser = null;
    cart = [];
    customerOrders = [];
    allAdminOrders = [];
    localStorage.removeItem('digibites_user');
    updateCartCount();

    const header = document.getElementById('main-header');
    if (header) header.classList.add('hidden');

    const sidebar = document.getElementById('sidebar');
    if (sidebar) sidebar.classList.remove('active');

    const overlay = document.getElementById('sidebar-overlay');
    if (overlay) overlay.classList.add('hidden');

    const appContainer = document.getElementById('app-container');
    if (appContainer) appContainer.classList.remove('admin-expanded');

    switchTab('login');
    showToast('Logged out successfully.');
}

// -------------------------------------------------------------
// 2. ROLE INTERFACE & NAVIGATION SETUP
// -------------------------------------------------------------
function setupUserInterface(user) {
    const header = document.getElementById('main-header');
    if (header) header.classList.remove('hidden');

    const userGreeting = document.getElementById('user-greeting');
    const userBadgeContainer = document.getElementById('user-badge-container');
    const appContainer = document.getElementById('app-container');
    const sidebarTitle = document.getElementById('sidebar-title');
    const navLinks = document.getElementById('sidebar-nav-links');

    if (!navLinks) return;

    if (user.role === 'admin') {
        // STAFF / ADMIN INTERFACE
        if (sidebarTitle) sidebarTitle.innerText = 'DigiBites Admin';
        if (userGreeting) userGreeting.innerText = `Staff: ${user.full_name}`;
        if (userBadgeContainer) userBadgeContainer.className = 'user-badge admin-badge';
        if (appContainer) appContainer.classList.add('admin-expanded');

        const staffNameEl = document.getElementById('staff-dash-name');
        if (staffNameEl) staffNameEl.innerText = user.full_name;

        navLinks.innerHTML = `
            <a href="javascript:void(0)" onclick="switchTab('staff-dashboard')"><i class="fa-solid fa-chart-line"></i> Staff Dashboard</a>
            <a href="javascript:void(0)" onclick="switchTab('admin-orders')"><i class="fa-solid fa-cash-register"></i> POS & Live Queue</a>
            <a href="javascript:void(0)" onclick="switchTab('admin-inventory')"><i class="fa-solid fa-boxes-stacked"></i> Products & Inventory</a>
            <a href="javascript:void(0)" onclick="switchTab('dashboard')"><i class="fa-solid fa-store"></i> Student View</a>
            <a href="javascript:void(0)" onclick="logout()"><i class="fa-solid fa-right-from-bracket"></i> Logout</a>
        `;

        loadStaffDashboard();
        switchTab('staff-dashboard');
    } else {
        // STUDENT / CUSTOMER INTERFACE
        if (sidebarTitle) sidebarTitle.innerText = 'DigiBites Menu';
        if (userGreeting) userGreeting.innerText = `Hi, ${user.full_name}!`;
        if (userBadgeContainer) userBadgeContainer.className = 'user-badge';
        if (appContainer) appContainer.classList.remove('admin-expanded');

        const studentNameEl = document.getElementById('student-dash-name');
        if (studentNameEl) studentNameEl.innerText = user.full_name;

        navLinks.innerHTML = `
            <a href="javascript:void(0)" onclick="switchTab('dashboard')"><i class="fa-solid fa-house"></i> Student Dashboard</a>
            <a href="javascript:void(0)" onclick="switchTab('specials')"><i class="fa-solid fa-utensils"></i> Today's Specials</a>
            <a href="javascript:void(0)" onclick="switchTab('cart')"><i class="fa-solid fa-cart-shopping"></i> Pre-Order Cart (<span class="cart-count">0</span>)</a>
            <a href="javascript:void(0)" onclick="switchTab('orders')"><i class="fa-solid fa-clock-rotate-left"></i> Order Status</a>
            <a href="javascript:void(0)" onclick="logout()"><i class="fa-solid fa-right-from-bracket"></i> Logout</a>
        `;

        loadStudentDashboard();
        switchTab('dashboard');
    }
}

function switchTab(viewId) {
    const views = ['login', 'dashboard', 'staff-dashboard', 'specials', 'cart', 'orders', 'admin-orders', 'admin-inventory'];
    views.forEach(id => {
        const el = document.getElementById(`view-${id}`);
        if (el) el.classList.add('hidden');
    });

    const activeView = document.getElementById(`view-${viewId}`);
    if (activeView) activeView.classList.remove('hidden');

    // Close sidebar
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('active');
    if (overlay) overlay.classList.add('hidden');

    // Render target view data
    if (viewId === 'dashboard') loadStudentDashboard();
    if (viewId === 'staff-dashboard') loadStaffDashboard();
    if (viewId === 'specials') renderMenuCatalog();
    if (viewId === 'cart') renderCart();
    if (viewId === 'orders') renderCustomerOrdersView();
    if (viewId === 'admin-orders') fetchAdminOrders();
    if (viewId === 'admin-inventory') renderAdminProductsTable();
}

// -------------------------------------------------------------
// 3. STUDENT DASHBOARD LOGIC
// -------------------------------------------------------------
async function loadStudentDashboard() {
    if (!currentUser) return;
    const nameEl = document.getElementById('student-dash-name');
    if (nameEl) nameEl.innerText = currentUser.full_name;

    // Fetch personal stats
    try {
        const res = await fetch(`/api/student/stats?student_id=${encodeURIComponent(currentUser.username)}`);
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.data) {
                const s = data.data;
                const ordersEl = document.getElementById('student-kpi-orders');
                const spentEl = document.getElementById('student-kpi-spent');
                if (ordersEl) ordersEl.innerText = s.total_orders;
                if (spentEl) spentEl.innerText = `₱${s.total_spent.toFixed(2)}`;
            }
        }
    } catch (e) {
        console.warn('Could not fetch student stats', e);
    }

    await fetchCustomerOrders();
    renderDashboardData();
}

// -------------------------------------------------------------
// 4. STAFF DASHBOARD LOGIC
// -------------------------------------------------------------
async function loadStaffDashboard() {
    try {
        const response = await fetch('/api/admin/stats');
        if (response.ok) {
            const res = await response.json();
            if (res.success && res.data) {
                adminStatsData = res.data;
                renderStaffKPIs(adminStatsData);
                renderStaffUrgentQueue(adminStatsData.recent_queue || []);
                renderStaffStockWatchlist(adminStatsData.low_stock_items || []);
            }
        }
    } catch (e) {
        console.warn('Error loading staff dashboard stats', e);
    }
}

function renderStaffKPIs(stats) {
    const salesEl = document.getElementById('kpi-today-sales');
    const queueEl = document.getElementById('kpi-active-queue');
    const completedEl = document.getElementById('kpi-completed-orders');
    const stockEl = document.getElementById('kpi-stock-alerts');

    if (salesEl) salesEl.innerText = `₱${stats.total_revenue.toFixed(2)}`;
    if (queueEl) queueEl.innerText = stats.active_orders;
    if (completedEl) completedEl.innerText = stats.completed_count;
    if (stockEl) stockEl.innerText = stats.low_stock_count;
}

function renderStaffUrgentQueue(queue) {
    const container = document.getElementById('staff-dash-queue-container');
    if (!container) return;

    if (queue.length === 0) {
        container.innerHTML = '<p class="empty-state">No urgent orders in queue. All clear!</p>';
        return;
    }

    let html = '';
    queue.forEach(o => {
        const itemsSummary = o.items.map(i => `${i.name} &times; ${i.qty}`).join(', ');
        const isWaiting = o.status === 'Waiting';
        const nextStatus = isWaiting ? 'Processing' : 'To Pickup';
        const nextLabel = isWaiting ? 'Start Preparing' : 'Ready for Pickup';
        const btnClass = isWaiting ? 'btn-status-proc' : 'btn-status-ready';

        html += `
            <div class="mini-feed-item">
                <div class="mini-feed-info">
                    <strong>${o.order_number}</strong> &bull; ${o.customer_name}
                    <p>${itemsSummary}</p>
                    <span style="font-size: 0.72rem; color: #64748b;">${o.created_at} &bull; ₱${o.total.toFixed(2)} (${o.payment_method})</span>
                </div>
                <div>
                    <button type="button" class="btn-status ${btnClass}" onclick="quickUpdateStatus(${o.order_id}, '${nextStatus}')">
                        ${nextLabel}
                    </button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function renderStaffStockWatchlist(items) {
    const container = document.getElementById('staff-dash-stock-container');
    if (!container) return;

    if (items.length === 0) {
        container.innerHTML = '<p class="empty-state" style="color: #166534;"><i class="fa-solid fa-circle-check"></i> All menu items are well stocked!</p>';
        return;
    }

    let html = '';
    items.forEach(item => {
        const isSoldOut = item.status === 'Sold Out' || item.stock_qty <= 0;
        const badgeColor = isSoldOut ? 'soldout' : 'nostock';
        html += `
            <div class="mini-feed-item">
                <div class="mini-feed-info">
                    <strong>${item.emoji || '🍲'} ${item.name}</strong> 
                    <span class="chip ${badgeColor}" style="padding: 2px 6px; font-size: 0.7rem; margin-left: 6px;">
                        ${isSoldOut ? 'Sold Out' : `Only ${item.stock_qty} left`}
                    </span>
                    <p>${item.canteen} Canteen &bull; ₱${item.price.toFixed(2)}</p>
                </div>
                <div>
                    <button type="button" class="btn-restock" onclick="quickRestockItem(${item.id})">
                        <i class="fa-solid fa-plus"></i> +10 Restock
                    </button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function quickUpdateStatus(orderId, newStatus) {
    await updateOrderStatus(orderId, newStatus);
    await loadStaffDashboard();
}

async function quickRestockItem(itemId) {
    try {
        const response = await fetch(`/api/menu/${itemId}/restock`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: 10 })
        });
        const res = await response.json();
        if (response.ok && res.success) {
            showToast(res.message || 'Restocked +10 items!');
            await loadMenu();
            await loadStaffDashboard();
        }
    } catch (e) {
        showToast('Error restocking item.');
    }
}

function refreshStaffDashboard() {
    loadStaffDashboard();
    fetchAdminOrders();
    showToast('Staff dashboard updated with live data.');
}

function openAddProductModal() {
    switchTab('admin-inventory');
    const form = document.getElementById('add-product-form');
    if (form && form.classList.contains('hidden')) {
        toggleAddProductForm();
    }
    const nameIn = document.getElementById('new-prod-name');
    if (nameIn) nameIn.focus();
}

// -------------------------------------------------------------
// 5. SYSTEM CONFIG & CATALOG LOADING (Zero Hardcoding)
// -------------------------------------------------------------
async function loadSystemConfig() {
    try {
        const response = await fetch('/api/config');
        if (response.ok) {
            const res = await response.json();
            if (res.success && res.data) {
                systemConfig = res.data;
                renderCategoryFilters();
                populatePaymentMethods();
            }
        }
    } catch (e) {
        console.warn('Could not load dynamic system config', e);
    }
}

async function loadMenu() {
    try {
        const response = await fetch('/api/menu');
        if (response.ok) {
            const res = await response.json();
            if (res.success && res.data) {
                menuItems = res.data;
                renderDashboardData();
                renderMenuCatalog();
                renderAdminProductsTable();
            }
        }
    } catch (e) {
        console.warn('Could not load menu', e);
    }
}

function renderCategoryFilters() {
    const container = document.getElementById('category-filter-container');
    if (!container) return;

    let html = `<button type="button" class="cat-pill ${currentCategoryFilter === 'all' ? 'active' : ''}" onclick="setCategoryFilter('all')">All Items</button>`;

    if (systemConfig.categories && systemConfig.categories.length > 0) {
        systemConfig.categories.forEach(cat => {
            const isActive = currentCategoryFilter === cat.code ? 'active' : '';
            html += `<button type="button" class="cat-pill ${isActive}" onclick="setCategoryFilter('${cat.code}')">${cat.name}</button>`;
        });
    }
    container.innerHTML = html;
}

function populatePaymentMethods() {
    const select = document.getElementById('cart-payment-method');
    if (!select) return;

    const methods = (systemConfig.settings && systemConfig.settings.payment_methods) || ["Cash on Pickup", "GCash", "Campus Card"];
    select.innerHTML = methods.map(m => `<option value="${m}">${m}</option>`).join('');
}

function setCategoryFilter(catCode) {
    currentCategoryFilter = catCode;
    renderCategoryFilters();
    renderMenuCatalog();
}

function filterMenuItems() {
    renderMenuCatalog();
}

// -------------------------------------------------------------
// 6. DYNAMIC MENU RENDERING & DASHBOARD
// -------------------------------------------------------------
function renderDashboardData() {
    // 1. Live Menu Availability Chips
    const chipsContainer = document.getElementById('dynamic-availability-chips');
    if (chipsContainer) {
        if (menuItems.length === 0) {
            chipsContainer.innerHTML = '<span class="chip nostock">No items in catalog</span>';
        } else {
            chipsContainer.innerHTML = menuItems.map(item => {
                const statusClass = item.status === 'Available' ? 'available' : (item.status === 'Sold Out' ? 'soldout' : 'nostock');
                const icon = item.status === 'Available' ? 'fa-circle-check' : 'fa-circle-xmark';
                return `<span class="chip ${statusClass}"><i class="fa-solid ${icon}"></i> ${item.name} (${item.status})</span>`;
            }).join('');
        }
    }

    // 2. Dynamic Canteen Counters
    const canteenGrid = document.getElementById('dynamic-canteen-grid');
    if (canteenGrid) {
        const canteens = systemConfig.canteens && systemConfig.canteens.length > 0
            ? systemConfig.canteens
            : [{ code: 'JHS', name: 'JHS Canteen' }, { code: 'SHS', name: 'SHS Canteen' }];

        canteenGrid.innerHTML = canteens.map(c => {
            const itemsInCanteen = menuItems.filter(i => i.canteen === c.code).slice(0, 4);
            const listHtml = itemsInCanteen.length > 0
                ? itemsInCanteen.map(i => `<li><strong>${i.name}</strong> - ₱${i.price.toFixed(2)}</li>`).join('')
                : '<li class="empty-state">No items listed.</li>';

            return `
                <div class="card canteen-card">
                    <h4><i class="fa-solid fa-location-dot"></i> ${c.name}</h4>
                    <ul>${listHtml}</ul>
                </div>
            `;
        }).join('');
    }

    renderActiveOrderTables();
}

function renderMenuCatalog() {
    const catalogContainer = document.getElementById('dynamic-menu-catalog');
    if (!catalogContainer) return;

    const searchInput = document.getElementById('menu-search-input');
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';

    let filtered = menuItems;
    if (currentCategoryFilter !== 'all') {
        filtered = filtered.filter(i => i.category.toLowerCase() === currentCategoryFilter.toLowerCase());
    }
    if (query) {
        filtered = filtered.filter(i => i.name.toLowerCase().includes(query) || i.canteen.toLowerCase().includes(query));
    }

    if (filtered.length === 0) {
        catalogContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-utensils" style="font-size: 2rem; color: #cbd5e1; margin-bottom: 8px;"></i>
                <p>No products match your filter.</p>
            </div>
        `;
        return;
    }

    let cardsHtml = '<div class="menu-grid">';
    filtered.forEach(item => {
        const isAvailable = item.status === 'Available' && item.stock_qty > 0;
        const soldOutClass = !isAvailable ? 'sold-out' : '';
        const btnHtml = isAvailable
            ? `<button type="button" onclick="addToCart('${item.name.replace(/'/g, "\\'")}', ${item.price})" class="btn btn-sm">Add to Cart</button>`
            : `<button type="button" class="btn btn-sm btn-disabled" disabled>Sold Out</button>`;

        cardsHtml += `
            <div class="menu-item-card ${soldOutClass}">
                <div class="item-img-placeholder">${item.emoji || '🍲'}</div>
                <div class="item-info">
                    <h4>${item.name}</h4>
                    <span class="badge">${item.canteen} CANTEEN</span>
                    <p class="price">₱${item.price.toFixed(2)}</p>
                    <div style="font-size: 0.75rem; color: #64748b; margin-bottom: 6px;">
                        ${isAvailable ? `Stock: ${item.stock_qty}` : 'Unavailable'}
                    </div>
                    ${btnHtml}
                </div>
            </div>
        `;
    });
    cardsHtml += '</div>';
    catalogContainer.innerHTML = cardsHtml;
}

// -------------------------------------------------------------
// 7. CART & PRE-ORDER OPERATIONS
// -------------------------------------------------------------
function addToCart(itemName, price) {
    const existing = cart.find(item => item.name === itemName);
    if (existing) {
        existing.qty += 1;
    } else {
        cart.push({ name: itemName, price: Number(price), qty: 1 });
    }
    updateCartCount();
    showToast(`${itemName} added to basket!`);
}

function changeQty(itemName, delta) {
    const item = cart.find(i => i.name === itemName);
    if (item) {
        item.qty += delta;
        if (item.qty <= 0) {
            cart = cart.filter(i => i.name !== itemName);
        }
        updateCartCount();
        renderCart();
    }
}

function removeFromCart(itemName) {
    cart = cart.filter(i => i.name !== itemName);
    updateCartCount();
    renderCart();
    showToast(`${itemName} removed.`);
}

function updateCartCount() {
    const count = cart.reduce((sum, item) => sum + item.qty, 0);
    document.querySelectorAll('.cart-count').forEach(el => {
        el.innerText = count;
    });
}

function renderCart() {
    const container = document.getElementById('cart-items-container');
    const totalEl = document.getElementById('cart-total-price');
    if (!container) return;

    container.innerHTML = '';
    let total = 0;

    if (cart.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-basket-shopping" style="font-size: 2.5rem; color: #cbd5e1; margin-bottom: 10px; display: block;"></i>
                <p>Your basket is empty.</p>
                <button type="button" class="btn btn-sm btn-primary" style="margin-top: 10px;" onclick="switchTab('specials')">Browse Menu</button>
            </div>
        `;
    } else {
        cart.forEach(item => {
            const itemTotal = item.price * item.qty;
            total += itemTotal;
            container.innerHTML += `
                <div class="cart-item-row">
                    <div class="cart-item-info">
                        <h4>${item.name}</h4>
                        <p>₱${item.price.toFixed(2)} each</p>
                        <div class="cart-qty-controls">
                            <button type="button" class="btn-qty" onclick="changeQty('${item.name.replace(/'/g, "\\'")}', -1)">-</button>
                            <span style="font-weight: bold; min-width: 20px; text-align: center;">${item.qty}</span>
                            <button type="button" class="btn-qty" onclick="changeQty('${item.name.replace(/'/g, "\\'")}', 1)">+</button>
                            <button type="button" class="btn-remove" onclick="removeFromCart('${item.name.replace(/'/g, "\\'")}')" title="Remove">
                                <i class="fa-solid fa-trash-can"></i>
                            </button>
                        </div>
                    </div>
                    <div>
                        <strong style="color: var(--primary-dark); font-size: 1.05rem;">₱${itemTotal.toFixed(2)}</strong>
                    </div>
                </div>
            `;
        });
    }

    if (totalEl) totalEl.innerText = `₱${total.toFixed(2)}`;
}

async function submitOrder() {
    if (cart.length === 0) {
        showToast('Your basket is empty!');
        return;
    }

    const paymentSelect = document.getElementById('cart-payment-method');
    const paymentMethod = paymentSelect ? paymentSelect.value : 'Cash on Pickup';

    const orderData = {
        student_id: currentUser ? currentUser.username : 'Guest',
        customer_name: currentUser ? currentUser.full_name : 'Guest Customer',
        items: [...cart],
        payment_method: paymentMethod
    };

    try {
        const response = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        const res = await response.json();
        if (response.ok && res.success) {
            customerOrders.unshift(res.order);
            cart = [];
            updateCartCount();
            showToast('Pre-order submitted successfully!');
            await loadMenu(); // Refresh stock
            switchTab('orders');
        } else {
            showToast(res.message || 'Error placing order.');
        }
    } catch (err) {
        showToast('Connection error placing order.');
    }
}

// -------------------------------------------------------------
// 8. CUSTOMER ORDERS & TRACKING
// -------------------------------------------------------------
async function fetchCustomerOrders() {
    if (!currentUser) return;
    try {
        const response = await fetch(`/api/orders?student_id=${encodeURIComponent(currentUser.username)}`);
        if (response.ok) {
            const result = await response.json();
            if (result.data) {
                customerOrders = result.data;
                renderActiveOrderTables();
                renderCustomerOrdersView();
            }
        }
    } catch (e) {
        console.warn('Error fetching customer orders', e);
    }
}

function renderActiveOrderTables() {
    const dashSummary = document.getElementById('active-order-summary');
    const ordersSummary = document.getElementById('orders-active-summary');
    const studentKpiActive = document.getElementById('student-kpi-active');

    // Find active order (Waiting, Processing, To Pickup)
    const activeOrder = customerOrders.find(o => o.status !== 'Completed' && o.status !== 'Cancelled');

    if (studentKpiActive) {
        studentKpiActive.innerText = activeOrder ? activeOrder.status : 'None';
        studentKpiActive.style.color = activeOrder ? 'var(--primary-dark)' : '#64748b';
    }

    let html = '';
    if (!activeOrder || !activeOrder.items || activeOrder.items.length === 0) {
        html = '<tr><td colspan="3" class="empty-state">No active orders right now.</td></tr>';
        updateProgressSteps('None', false);
    } else {
        activeOrder.items.forEach(item => {
            html += `<tr><td>${item.name}</td><td>x${item.qty}</td><td>₱${(item.price * item.qty).toFixed(2)}</td></tr>`;
        });
        updateProgressSteps(activeOrder.status || 'Waiting', true);
    }

    if (dashSummary) dashSummary.innerHTML = html;
    if (ordersSummary) ordersSummary.innerHTML = html;
}

function updateProgressSteps(status, hasOrder) {
    const step1List = [document.getElementById('dash-step-1'), document.getElementById('orders-step-1')];
    const step2List = [document.getElementById('dash-step-2'), document.getElementById('orders-step-2')];
    const step3List = [document.getElementById('dash-step-3'), document.getElementById('orders-step-3')];

    step1List.forEach(el => el && el.classList.remove('active'));
    step2List.forEach(el => el && el.classList.remove('active'));
    step3List.forEach(el => el && el.classList.remove('active'));

    if (!hasOrder) return;

    if (status === 'Waiting') {
        step1List.forEach(el => el && el.classList.add('active'));
    } else if (status === 'Processing') {
        step1List.forEach(el => el && el.classList.add('active'));
        step2List.forEach(el => el && el.classList.add('active'));
    } else if (status === 'To Pickup' || status === 'Completed') {
        step1List.forEach(el => el && el.classList.add('active'));
        step2List.forEach(el => el && el.classList.add('active'));
        step3List.forEach(el => el && el.classList.add('active'));
    }
}

function renderCustomerOrdersView() {
    renderActiveOrderTables();
    const historyContainer = document.getElementById('order-history-list');
    if (!historyContainer) return;

    if (customerOrders.length === 0) {
        historyContainer.innerHTML = '<p class="empty-state">No order history available.</p>';
        return;
    }

    let historyHtml = '';
    customerOrders.forEach(order => {
        const itemsText = order.items.map(i => `${i.name} (x${i.qty})`).join(', ');
        const statusClass = order.status === 'Completed' ? 'available' : (order.status === 'Cancelled' ? 'soldout' : 'nostock');

        historyHtml += `
            <div class="order-history-card">
                <div class="order-header">
                    <span>${order.order_number || `Order #${order.order_id}`}</span>
                    <span class="chip ${statusClass}">${order.status}</span>
                </div>
                <p style="font-size: 0.85rem; color: #475569; margin: 4px 0;">${itemsText}</p>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 6px;">
                    <span style="font-size: 0.78rem; color: #64748b;">
                        <i class="fa-solid fa-clock"></i> ${order.created_at || 'Just now'} &bull; ${order.payment_method}
                    </span>
                    <strong style="color: var(--primary-dark); font-size: 0.95rem;">₱${order.total.toFixed(2)}</strong>
                </div>
            </div>
        `;
    });
    historyContainer.innerHTML = historyHtml;
}

// -------------------------------------------------------------
// 9. ADMIN / POS OPERATIONS
// -------------------------------------------------------------
async function fetchAdminOrders() {
    try {
        const response = await fetch('/api/orders?role=admin');
        if (response.ok) {
            const res = await response.json();
            if (res.success && res.data) {
                allAdminOrders = res.data;
                renderAdminOrdersQueue();
                loadStaffDashboard();
            }
        }
    } catch (e) {
        console.warn('Error loading admin orders', e);
    }
}

function filterAdminOrders(status) {
    currentAdminOrderFilter = status;
    const filterButtons = document.querySelectorAll('#view-admin-orders .cat-pill');
    filterButtons.forEach(btn => {
        if (btn.innerText.includes(status)) btn.classList.add('active');
        else btn.classList.remove('active');
    });
    renderAdminOrdersQueue();
}

function renderAdminOrdersQueue() {
    const container = document.getElementById('admin-orders-container');
    if (!container) return;

    let filtered = allAdminOrders;
    if (currentAdminOrderFilter !== 'All') {
        filtered = filtered.filter(o => o.status === currentAdminOrderFilter);
    }

    if (filtered.length === 0) {
        container.innerHTML = '<p class="empty-state">No orders in this queue.</p>';
        return;
    }

    let html = '';
    filtered.forEach(order => {
        const itemsList = order.items.map(i => `<li>${i.name} &times; ${i.qty} (₱${(i.price * i.qty).toFixed(2)})</li>`).join('');
        const isPaid = order.payment_status === 'Paid';
        const payBadge = isPaid
            ? `<span class="chip available"><i class="fa-solid fa-check"></i> Paid</span>`
            : `<span class="chip soldout"><i class="fa-solid fa-xmark"></i> Unpaid</span>`;

        html += `
            <div class="pos-order-card">
                <div class="pos-order-header">
                    <div>
                        <strong>${order.order_number || `Order #${order.order_id}`}</strong>
                        <span style="font-size: 0.8rem; color: #64748b; margin-left: 6px;">Customer: ${order.customer_name}</span>
                    </div>
                    <div>
                        ${payBadge}
                        <span class="chip nostock" style="margin-left: 4px;">${order.status}</span>
                    </div>
                </div>
                <ul style="font-size: 0.85rem; color: #334155; margin: 8px 0; padding-left: 20px;">
                    ${itemsList}
                </ul>
                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px dashed #fed7aa; padding-top: 6px;">
                    <span style="font-size: 0.8rem; color: #64748b;">Method: ${order.payment_method}</span>
                    <strong style="font-size: 1.05rem; color: var(--primary-dark);">Total: ₱${order.total.toFixed(2)}</strong>
                </div>
                <div class="pos-actions">
                    <button type="button" class="btn-status btn-status-proc" onclick="updateOrderStatus(${order.order_id}, 'Processing')">
                        <i class="fa-solid fa-fire"></i> Preparing
                    </button>
                    <button type="button" class="btn-status btn-status-ready" onclick="updateOrderStatus(${order.order_id}, 'To Pickup')">
                        <i class="fa-solid fa-bell"></i> Ready
                    </button>
                    <button type="button" class="btn-status btn-status-done" onclick="updateOrderStatus(${order.order_id}, 'Completed')">
                        <i class="fa-solid fa-check-circle"></i> Complete
                    </button>
                    <button type="button" class="btn-status btn-status-pay" onclick="toggleOrderPayment(${order.order_id}, '${isPaid ? 'Unpaid' : 'Paid'}')">
                        <i class="fa-solid fa-money-bill-wave"></i> ${isPaid ? 'Mark Unpaid' : 'Mark Paid'}
                    </button>
                    <button type="button" class="btn-status btn-status-cancel" onclick="updateOrderStatus(${order.order_id}, 'Cancelled')">
                        <i class="fa-solid fa-ban"></i>
                    </button>
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

async function updateOrderStatus(orderId, newStatus) {
    try {
        const response = await fetch(`/api/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const res = await response.json();
        if (response.ok && res.success) {
            showToast(`Order updated to ${newStatus}`);
            fetchAdminOrders();
            loadStaffDashboard();
        } else {
            showToast(res.message || 'Failed to update order.');
        }
    } catch (e) {
        showToast('Error communicating with server.');
    }
}

async function toggleOrderPayment(orderId, paymentStatus) {
    try {
        const response = await fetch(`/api/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ payment_status: paymentStatus })
        });
        const res = await response.json();
        if (response.ok && res.success) {
            showToast(`Payment marked as ${paymentStatus}`);
            fetchAdminOrders();
            loadStaffDashboard();
        }
    } catch (e) {
        showToast('Error updating payment status.');
    }
}

// -------------------------------------------------------------
// 10. ADMIN PRODUCTS & INVENTORY MANAGEMENT
// -------------------------------------------------------------
function toggleAddProductForm() {
    const form = document.getElementById('add-product-form');
    const icon = document.getElementById('add-prod-icon');
    if (form) {
        form.classList.toggle('hidden');
        if (icon) {
            icon.className = form.classList.contains('hidden') ? 'fa-solid fa-chevron-down' : 'fa-solid fa-chevron-up';
        }
    }
}

async function handleCreateProduct(event) {
    if (event) event.preventDefault();
    const name = document.getElementById('new-prod-name').value.trim();
    const price = parseFloat(document.getElementById('new-prod-price').value);
    const stock = parseInt(document.getElementById('new-prod-stock').value, 10);
    const canteen = document.getElementById('new-prod-canteen').value;
    const category = document.getElementById('new-prod-category').value;
    const status = document.getElementById('new-prod-status').value;
    const emoji = document.getElementById('new-prod-emoji').value.trim() || '🍲';

    if (!name || isNaN(price) || price <= 0) {
        showToast('Please provide a valid product name and price.');
        return;
    }

    try {
        const response = await fetch('/api/menu', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, price, stock_qty: stock, canteen, category, status, emoji })
        });
        const res = await response.json();

        if (response.ok && res.success) {
            showToast(`Product '${name}' added!`);
            document.getElementById('new-prod-name').value = '';
            document.getElementById('new-prod-price').value = '';
            toggleAddProductForm();
            await loadMenu();
            loadStaffDashboard();
        } else {
            showToast(res.message || 'Failed to add product.');
        }
    } catch (e) {
        showToast('Server error while adding product.');
    }
}

function renderAdminProductsTable() {
    const tbody = document.getElementById('admin-products-table-body');
    const countBadge = document.getElementById('product-count-badge');
    if (!tbody) return;

    if (countBadge) countBadge.innerText = `${menuItems.length} Items`;

    if (menuItems.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No products registered in database.</td></tr>';
        return;
    }

    let html = '';
    menuItems.forEach(item => {
        const isAvail = item.status === 'Available';
        const stockClass = item.stock_qty <= 5 ? 'low' : 'ok';
        html += `
            <tr>
                <td>
                    <span style="font-size: 1.1rem; margin-right: 4px;">${item.emoji || '🍲'}</span>
                    <strong>${item.name}</strong><br>
                    <small style="color: #64748b;">${item.canteen} &bull; ${item.category}</small>
                </td>
                <td>₱${item.price.toFixed(2)}</td>
                <td><span class="stock-pill ${stockClass}">${item.stock_qty}</span></td>
                <td>
                    <span class="chip ${isAvail ? 'available' : 'soldout'}" style="padding: 2px 6px; font-size: 0.7rem;">
                        ${item.status}
                    </span>
                </td>
                <td>
                    <div style="display: flex; gap: 4px;">
                        <button type="button" class="btn-status ${isAvail ? 'btn-status-cancel' : 'btn-status-ready'}" 
                                onclick="toggleProductAvailability(${item.id}, '${isAvail ? 'Sold Out' : 'Available'}')">
                            ${isAvail ? 'Sold Out' : 'Make Avail'}
                        </button>
                        <button type="button" class="btn-remove" onclick="deleteProduct(${item.id})" title="Delete">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
    tbody.innerHTML = html;
}

async function toggleProductAvailability(itemId, newStatus) {
    try {
        const response = await fetch(`/api/menu/${itemId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        const res = await response.json();
        if (response.ok && res.success) {
            showToast(`Product set to ${newStatus}`);
            await loadMenu();
            loadStaffDashboard();
        }
    } catch (e) {
        showToast('Error updating product status.');
    }
}

async function deleteProduct(itemId) {
    if (!confirm('Are you sure you want to delete this product from the database?')) return;
    try {
        const response = await fetch(`/api/menu/${itemId}`, { method: 'DELETE' });
        const res = await response.json();
        if (response.ok && res.success) {
            showToast('Product removed.');
            await loadMenu();
            loadStaffDashboard();
        }
    } catch (e) {
        showToast('Error deleting product.');
    }
}

// -------------------------------------------------------------
// 11. UTILITY TOAST NOTIFICATIONS
// -------------------------------------------------------------
function showToast(message) {
    const existing = document.querySelector('.toast-notification');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.innerText = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 2800);
}