from flask import Flask, render_template, send_file, request, jsonify, session, redirect
from flask_socketio import SocketIO, emit, join_room, leave_room
import threading
from flask_cors import CORS
from functools import wraps
import sqlite3
import json
from datetime import datetime, timedelta
import pytz
from datetime import timedelta
import hashlib
import secrets

app = Flask(__name__)
app.secret_key = "932f51871ac9f83ec62574c3503be7171923cf9b4a2caa460cb389b195a8b021"

def get_db_time():
    """Get Jakarta timezone aware datetime string for database"""
    return datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Background thread untuk monitor stock
def monitor_stock():
    """Monitor stock setiap 5 detik"""
    while True:
        try:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('''
                SELECT id, barcode, name, stock, minimum_stock 
                FROM products 
                WHERE stock < minimum_stock
            ''')
            low_stock_items = cursor.fetchall()
            db.close()
            
            if low_stock_items:
                for item in low_stock_items:
                    socketio.emit('stock_alert', {
                        'id': item['id'],
                        'barcode': item['barcode'],
                        'name': item['name'],
                        'stock': item['stock'],
                        'minimum_stock': item['minimum_stock'],
                        'status': 'CRITICAL' if item['stock'] == 0 else 'LOW',
                        'timestamp': datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S %Z')
                    }, room='admin_room')
            
            import time
            time.sleep(5)
        except Exception as e:
            print(f"Error monitoring: {e}")
            import time
            time.sleep(5)

monitor_thread = threading.Thread(target=monitor_stock, daemon=True)
monitor_thread.start()

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('join_admin')
def handle_join_admin():
    join_room('admin_room')
    emit('status', {'msg': 'Terhubung'})

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    leave_room('admin_room')

DB_PATH = 'kasir.db'

def hash_password(password):
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${hashed.hex()}"

def verify_password(stored_hash, password):
    try:
        salt, hashed = stored_hash.split('$')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return new_hash.hex() == hashed
    except:
        return False

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        barcode TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        price INTEGER NOT NULL,
        stock INTEGER DEFAULT 100,
        minimum_stock INTEGER DEFAULT 20,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        items_json TEXT NOT NULL,
        total_amount INTEGER NOT NULL,
        payment_method TEXT NOT NULL,
        payment_status TEXT DEFAULT 'completed',
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS inventory_logs (
        id INTEGER PRIMARY KEY,
        barcode TEXT NOT NULL,
        product_name TEXT NOT NULL,
        quantity_change INTEGER NOT NULL,
        action TEXT NOT NULL,
        user_id INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS stock_alerts (
        id INTEGER PRIMARY KEY,
        barcode TEXT NOT NULL,
        product_name TEXT NOT NULL,
        current_stock INTEGER NOT NULL,
        minimum_stock INTEGER NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    cursor.execute("""CREATE TABLE IF NOT EXISTS login_logs (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        username TEXT,
        action TEXT,
        ip_address TEXT,
        user_agent TEXT,
        success BOOLEAN,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id))""")
    
    cursor.execute('SELECT COUNT(*) as count FROM users')
    if cursor.fetchone()['count'] == 0:
        print("Creating users...")
        admin_hash = hash_password('admin123')
        kasir1_hash = hash_password('kasir123')
        kasir2_hash = hash_password('kasir123')
        
        cursor.execute('INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)',
                      ('admin', admin_hash, 'Administrator', 'admin'))
        cursor.execute('INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)',
                      ('kasir1', kasir1_hash, 'Kasir 1', 'kasir'))
        cursor.execute('INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)',
                      ('kasir2', kasir2_hash, 'Kasir 2', 'kasir'))
        
        cursor.execute('SELECT username, role FROM users')
        users = cursor.fetchall()
        print(f"Created {len(users)} users:")
        for u in users:
            print(f"  - {u['username']} ({u['role']})")
    
    cursor.execute('SELECT COUNT(*) as count FROM products')
    if cursor.fetchone()['count'] == 0:
        products = [
            ('8992700100097', 'Indomie Goreng', 2500, 50),
            ('8992700100110', 'Indomie Kuah Ayam', 2500, 50),
            ('8992711400029', 'Mie Sedaap Goreng', 3000, 50),
            ('4001200006008', 'Aqua 600ml', 5000, 100),
            ('8998888100010', 'Coca Cola 250ml', 4500, 80),
            ('8888000100001', 'Sprite 250ml', 4500, 80),
            ('8999999900001', 'Teh Sosro', 3000, 60),
            ('7777777700001', 'Roti Tawar', 8000, 30),
        ]
        for barcode, name, price, stock in products:
            cursor.execute('INSERT INTO products (barcode, name, price, stock, minimum_stock) VALUES (?, ?, ?, ?, ?)',
                          (barcode, name, price, stock, 20))
    
    db.commit()
    db.close()
    print('✅ Database initialized')

init_db()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        if 'login_time' in session:
            login_time = datetime.fromisoformat(session['login_time'])
            if datetime.now() - login_time > timedelta(hours=24):
                session.clear()
                return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect('/login')
            if session.get('role') != required_role and session.get('role') != 'admin':
                return jsonify({'success': False, 'message': 'Akses ditolak'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    if 'user_id' in session:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, full_name, role FROM users WHERE id = ?', (session['user_id'],))
        user = cursor.fetchone()
        db.close()
        return user
    return None

def log_login(username, success, user_id=None):
    try:
        db = get_db()
        cursor = db.cursor()
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')
        cursor.execute('INSERT INTO login_logs (user_id, username, action, ip_address, user_agent, success) VALUES (?, ?, ?, ?, ?, ?)',
                      (user_id, username, 'LOGIN' if success else 'LOGIN_FAILED', ip_address, user_agent, success))
        db.commit()
        db.close()
    except Exception as e:
        print(f"Error logging login: {e}")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            log_login(username, False)
            return jsonify({'success': False, 'message': 'Username dan password harus diisi'}), 400
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT id, username, password_hash, full_name, role, is_active FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        db.close()
        
        if user and verify_password(user['password_hash'], password) and user['is_active']:
            db = get_db()
            cursor = db.cursor()
            cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
            db.commit()
            db.close()
            
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['login_time'] = datetime.now().isoformat()
            
            log_login(username, True, user['id'])
            
            redirect_url = '/'
            if user['role'] == 'admin':
                redirect_url = '/admin'
            elif user['role'] == 'manager':
                redirect_url = '/manager'
            
            return jsonify({'success': True, 'redirect': redirect_url}), 200
        
        log_login(username, False, user['id'] if user else None)
        return jsonify({'success': False, 'message': 'Username atau password salah'}), 401
    
    return '''<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - SmartKasir</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 420px;
            padding: 40px;
        }
        .logo { text-align: center; margin-bottom: 30px; }
        .logo h1 { font-size: 32px; color: #1f2937; margin-bottom: 8px; }
        .logo p { color: #6b7280; font-size: 14px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 600; color: #1f2937; }
        .input-wrapper { position: relative; }
        input[type="text"], input[type="password"] {
            width: 100%; padding: 12px 14px; border: 2px solid #e5e7eb;
            border-radius: 8px; font-size: 14px;
        }
        .toggle-password {
            position: absolute; right: 12px; top: 50%; transform: translateY(-50%);
            background: none; border: none; cursor: pointer; color: #6b7280; font-size: 18px;
        }
        .login-btn {
            width: 100%; padding: 12px; background: #667eea; color: white;
            border: none; border-radius: 8px; font-size: 15px; font-weight: 600;
            cursor: pointer; margin-top: 24px;
        }
        .error {
            background: #fee2e2; border: 1px solid #fecaca; color: #dc2626;
            padding: 12px; border-radius: 8px; margin-bottom: 16px;
            font-size: 14px; display: none;
        }
        .error.show { display: block; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">
            <h1>🛒 SmartKasir</h1>
            <p>Sistem POS Modern</p>
        </div>
        <div id="error" class="error"></div>
        <form id="loginForm">
            <div class="form-group">
                <label for="username">👤 Username</label>
                <input type="text" id="username" name="username" placeholder="Masukkan username..." autofocus required>
            </div>
            <div class="form-group">
                <label for="password">🔐 Kata Sandi</label>
                <div class="input-wrapper">
                    <input type="password" id="password" name="password" placeholder="Masukkan kata sandi..." required>
                    <button type="button" class="toggle-password" id="togglePassword">👁️</button>
                </div>
            </div>
            <button type="submit" class="login-btn">🔓 Login</button>
        </form>
    </div>
    <script>
        const passwordInput = document.getElementById('password');
        const togglePassword = document.getElementById('togglePassword');
        togglePassword.addEventListener('click', function(e) {
            e.preventDefault();
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                togglePassword.textContent = '🙈';
            } else {
                passwordInput.type = 'password';
                togglePassword.textContent = '👁️';
            }
        });
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            const errorEl = document.getElementById('error');
            fetch('/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            }).then(r => r.json()).then(data => {
                if (data.success) {
                    window.location.href = data.redirect;
                } else {
                    errorEl.textContent = data.message;
                    errorEl.classList.add('show');
                }
            });
        });
    </script>
</body>
</html>'''

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@login_required
def index():
    return send_file('index.html')

@app.route('/inventory')
@login_required
def inventory_page():
    return send_file('inventory.html')

@app.route('/manager')
@login_required
def manager_page():
    return send_file('manager.html')

@app.route('/api/user', methods=['GET'])
@login_required
def get_user_info():
    user = get_current_user()
    if user:
        return jsonify({'success': True, 'id': user['id'], 'username': user['username'], 'full_name': user['full_name'], 'role': user['role']}), 200
    return jsonify({'success': False, 'message': 'Not logged in'}), 401

@app.route('/product/<barcode>', methods=['GET'])
@login_required
def get_product(barcode):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM products WHERE barcode = ?', (barcode,))
        product = cursor.fetchone()
        db.close()
        if not product:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        return jsonify({'success': True, 'product': {'barcode': product['barcode'], 'name': product['name'], 'price': product['price'], 'stock': product['stock']}}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        nominal = data.get('nominal', 0)
        user = get_current_user()
        user_id = user['id'] if user else None
        cart_data = data.get('cart', {})
        
        if not cart_data:
            return jsonify({'success': False, 'message': 'Keranjang kosong'}), 400
        
        total = sum(item['price'] * item['qty'] for item in cart_data.values())
        
        if payment_method == 'tunai' and nominal < total:
            return jsonify({'success': False, 'message': 'Nominal kurang'}), 400
        
        db = get_db()
        cursor = db.cursor()
        items_json = json.dumps(cart_data)
        cursor.execute('INSERT INTO transactions (items_json, total_amount, payment_method, user_id, created_at) VALUES (?, ?, ?, ?, ?)',
                      (items_json, total, payment_method, user_id, get_db_time()))
        db.commit()
        transaction_id = cursor.lastrowid
        
        for barcode, item in cart_data.items():
            cursor.execute('SELECT stock, minimum_stock FROM products WHERE barcode = ?', (barcode,))
            product = cursor.fetchone()
            if product:
                new_stock = product['stock'] - item['qty']
                cursor.execute('UPDATE products SET stock = ? WHERE barcode = ?', (new_stock, barcode))
                cursor.execute('INSERT INTO inventory_logs (barcode, product_name, quantity_change, action, user_id) VALUES (?, ?, ?, ?, ?)',
                              (barcode, item['name'], -item['qty'], 'sold', user_id))
                if new_stock < product['minimum_stock']:
                    cursor.execute('INSERT INTO stock_alerts (barcode, product_name, current_stock, minimum_stock, status) VALUES (?, ?, ?, ?, ?)',
                                  (barcode, item['name'], new_stock, product['minimum_stock'], 'alert'))
        
        db.commit()
        db.close()
        return jsonify({'success': True, 'invoice_number': transaction_id, 'total': total, 'payment_method': payment_method}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/inventory/stock/<barcode>', methods=['GET'])
@login_required
def get_stock(barcode):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT barcode, name, price, stock, minimum_stock FROM products WHERE barcode = ?', (barcode,))
        product = cursor.fetchone()
        db.close()
        if not product:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        return jsonify({'success': True, 'barcode': product['barcode'], 'name': product['name'], 'price': product['price'], 'stock': product['stock'], 'minimum_stock': product['minimum_stock'], 'status': 'warning' if product['stock'] < product['minimum_stock'] else 'ok'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/manager/stock-alerts', methods=['GET'])
@login_required
def get_detailed_stock_alerts():
    """Get detailed stock alerts with urgency levels and predictions"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Get all products with stock below minimum
        cursor.execute("""
            SELECT id, barcode, name, stock, minimum_stock 
            FROM products 
            WHERE stock < minimum_stock
            ORDER BY stock ASC
        """)
        products = cursor.fetchall()
        
        alerts = []
        for product in products:
            barcode = product['barcode']
            current_stock = product['stock']
            minimum_stock = product['minimum_stock']
            
            # Calculate urgency: critical (0-50%), warning (50-80%), normal (80%+)
            stock_percent = (current_stock / minimum_stock * 100) if minimum_stock > 0 else 0
            
            if stock_percent < 20:
                urgency = 'critical'
                urgency_level = 1
            elif stock_percent < 50:
                urgency = 'warning'
                urgency_level = 2
            else:
                urgency = 'normal'
                urgency_level = 3
            
            # Simple prediction: days to stockout
            cursor.execute("""
                SELECT COUNT(*) as sales_count FROM inventory_logs
                WHERE barcode = ? AND action = 'sold'
                AND created_at >= datetime('now', '-7 days')
            """, (barcode,))
            weekly_sales = cursor.fetchone()['sales_count']
            
            daily_sales = weekly_sales / 7 if weekly_sales > 0 else 1
            days_to_stockout = int(current_stock / daily_sales) if daily_sales > 0 else 999
            
            # Recommend reorder quantity (2 months supply)
            recommended_reorder = int(daily_sales * 60)
            
            alerts.append({
                'id': product['id'],
                'barcode': barcode,
                'name': product['name'],
                'currentStock': current_stock,
                'minimumStock': minimum_stock,
                'urgency': urgency,
                'urgencyLevel': urgency_level,
                'daysToStockout': max(0, days_to_stockout),
                'dailySales': round(daily_sales, 2),
                'recommendedReorder': recommended_reorder,
                'stockPercent': round(stock_percent, 1)
            })
        
        # Sort by urgency level
        alerts.sort(key=lambda x: x['urgencyLevel'])
        
        db.close()
        
        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': alerts
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500



@app.route('/inventory/logs', methods=['GET'])
@login_required
def get_inventory_logs():
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT * FROM inventory_logs ORDER BY created_at DESC LIMIT 100')
        logs = cursor.fetchall()
        db.close()
        return jsonify({'success': True, 'logs': [dict(l) for l in logs]}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/receipt/<int:transaction_id>', methods=['GET'])
@login_required
def get_receipt(transaction_id):
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT t.id, t.items_json, t.total_amount, t.payment_method, t.created_at, u.full_name FROM transactions t LEFT JOIN users u ON t.user_id = u.id WHERE t.id = ?', (transaction_id,))
        transaction = cursor.fetchone()
        db.close()
        
        if not transaction:
            return jsonify({'success': False, 'message': 'Receipt tidak ditemukan'}), 404
        
        items = json.loads(transaction['items_json'])
        receipt = "=" * 40 + "\n         SMARTKASIR\n" + "=" * 40 + "\n"
        receipt += f"Invoice: #{transaction['id']}\nTanggal: {transaction['created_at']}\n" + "-" * 40 + "\n"
        
        for barcode, item in items.items():
            name = item['name'][:20]
            qty = item['qty']
            price = item['price']
            subtotal = qty * price
            receipt += f"{name}\n  {qty}x Rp {price:,} = Rp {subtotal:,}\n"
        
        receipt += "-" * 40 + f"\nTOTAL             Rp {transaction['total_amount']:,}\n" + "=" * 40 + "\n"
        
        return jsonify({'success': True, 'receipt': receipt, 'transaction_id': transaction_id}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


def get_period_date_range(period):
    """Get start and end date based on period"""
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    
    if period == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = 'Today'
    elif period == '7days':
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        start = end - timedelta(days=7)
        label = 'Last 7 Days'
    elif period == '30days':
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        start = end - timedelta(days=30)
        label = 'Last 30 Days'
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = 'Today'
    
    return (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'), label)

def calculate_health_score(transactions, stock_alerts):
    """Calculate business health score (0-100)"""
    health_score = 50
    total_tx = len(transactions)
    if total_tx > 10:
        health_score += min(20, total_tx // 5)
    health_score += 15
    if stock_alerts == 0:
        health_score += 15
    elif stock_alerts <= 5:
        health_score += 10
    else:
        health_score -= min(10, stock_alerts * 2)
    return min(100, max(0, health_score))

@app.route('/api/manager/analytics', methods=['GET'])
@login_required
def manager_analytics():
    try:
        period = request.args.get('period', 'today')
        db = get_db()
        cursor = db.cursor()
        start_date, end_date, label = get_period_date_range(period)
        cursor.execute("SELECT * FROM transactions WHERE created_at >= ? AND created_at <= ? ORDER BY created_at DESC", (start_date, end_date))
        transactions = cursor.fetchall()
        total_revenue = sum(t['total_amount'] for t in transactions)
        total_tx = len(transactions)
        avg_tx = total_revenue / total_tx if total_tx > 0 else 0
        total_profit = total_revenue * 0.30
        cursor.execute("SELECT COUNT(*) as count FROM stock_alerts WHERE status = 'alert'")
        stock_alerts = cursor.fetchone()['count']
        top_products = {}
        for tx in transactions:
            items = json.loads(tx['items_json'])
            for barcode, item in items.items():
                if barcode not in top_products:
                    top_products[barcode] = {'barcode': barcode, 'name': item['name'], 'qty': 0, 'revenue': 0}
                top_products[barcode]['qty'] += item['qty']
                top_products[barcode]['revenue'] += item['price'] * item['qty']
        top_products_list = sorted(top_products.values(), key=lambda x: x['revenue'], reverse=True)[:5]
        revenue_trend = []
        if period == 'today':
            hourly_data = {}
            for tx in transactions:
                hour = tx['created_at'][11:13]
                if hour not in hourly_data:
                    hourly_data[hour] = 0
                hourly_data[hour] += tx['total_amount']
            for h in range(24):
                hour_str = f"{h:02d}:00"
                revenue_trend.append({'label': hour_str, 'revenue': hourly_data.get(f"{h:02d}", 0)})
        else:
            daily_data = {}
            for tx in transactions:
                date = tx['created_at'][:10]
                if date not in daily_data:
                    daily_data[date] = 0
                daily_data[date] += tx['total_amount']
            revenue_trend = [{'label': k, 'revenue': v} for k, v in sorted(daily_data.items())]
        health_score = calculate_health_score(transactions, stock_alerts)
        db.close()
        return jsonify({'success': True, 'period': period, 'periodLabel': label, 'totalRevenue': total_revenue, 'totalTransactions': total_tx, 'avgTransaction': round(avg_tx, 0), 'totalProfit': round(total_profit, 0), 'profitMargin': 30.0, 'topProducts': top_products_list, 'stockAlerts': stock_alerts, 'revenueTrend': revenue_trend, 'healthScore': health_score}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/manager/recommendations', methods=['GET'])
@login_required
def manager_recommendations():
    return jsonify({
        'success': True,
        'recommendations': [
            {'type': 'success', 'title': '✅ Indomie Best Seller', 'description': 'Top seller dengan 15 pcs terjual.'},
            {'type': 'warning', 'title': '⚠️ Aqua Stock Rendah', 'description': 'Stok 8 pcs, minimum 20 pcs.'},
            {'type': 'danger', 'title': '❌ Roti Slow Moving', 'description': 'Hanya 1 pcs terjual.'},
            {'type': 'success', 'title': '💡 Bundle Promo', 'description': 'Indomie + Minuman dengan harga spesial.'}
        ]
    }), 200


@app.route('/api/products', methods=['GET'])
@login_required
def get_products():
    """Get all products with real stock"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        search = request.args.get('search', '').lower()
        
        query = 'SELECT * FROM products'
        params = []
        
        if search:
            query += ' WHERE (name LIKE ? OR barcode LIKE ?)'
            params = [f'%{search}%', f'%{search}%']
        
        cursor.execute(query, params)
        products = cursor.fetchall()
        db.close()
        
        result = []
        for p in products:
            icon = '🍜' if 'ndomie' in p['name'].lower() or 'mie' in p['name'].lower() else                    '💧' if 'aqua' in p['name'].lower() else                    '🥤' if any(x in p['name'].lower() for x in ['cola', 'sprite', 'teh']) else                    '🍞' if 'roti' in p['name'].lower() else '📦'
            
            result.append({
                'barcode': p['barcode'],
                'name': p['name'],
                'price': p['price'],
                'stock': p['stock'],
                'minimum_stock': p['minimum_stock'],
                'icon': icon,
                'status': 'warning' if p['stock'] < p['minimum_stock'] else 'ok'
            })
        
        return jsonify({'success': True, 'products': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/product/search', methods=['POST'])
@login_required
def search_product():
    """Search product by barcode"""
    try:
        data = request.get_json()
        barcode = data.get('barcode', '').strip()
        
        if not barcode:
            return jsonify({'success': False, 'message': 'Barcode kosong'}), 400
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT barcode, name, price, stock FROM products WHERE barcode = ?', (barcode,))
        product = cursor.fetchone()
        db.close()
        
        if not product:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        
        if product['stock'] <= 0:
            return jsonify({'success': False, 'message': 'Produk habis'}), 400
        
        icon = '🍜' if 'ndomie' in product['name'].lower() else '🥤' if 'cola' in product['name'].lower() else '📦'
        
        return jsonify({
            'success': True,
            'product': {
                'barcode': product['barcode'],
                'name': product['name'],
                'price': product['price'],
                'stock': product['stock'],
                'icon': icon
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/products/low-stock', methods=['GET'])
@login_required
def get_low_stock():
    """Get low stock products"""
    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute('SELECT barcode, name, stock, minimum_stock FROM products WHERE stock < minimum_stock ORDER BY stock ASC')
        products = cursor.fetchall()
        db.close()
        
        result = [dict(p) for p in products]
        
        return jsonify({'success': True, 'alerts': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/transactions/today', methods=['GET'])
@login_required
def get_today_transactions():
    """Get transactions for today"""
    try:
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute("""
            SELECT t.id, t.total_amount, t.payment_method, t.created_at, u.full_name
            FROM transactions t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE DATE(t.created_at) = DATE('now')
            ORDER BY t.created_at DESC
            LIMIT 20
        """)
        
        transactions = cursor.fetchall()
        db.close()
        
        result = []
        for tx in transactions:
            result.append({
                'id': tx['id'],
                'amount': tx['total_amount'],
                'method': tx['payment_method'],
                'time': tx['created_at'],
                'cashier': tx['full_name']
            })
        
        return jsonify({'success': True, 'transactions': result}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/stock-monitor')
@login_required
def stock_monitor():
    # ... paste code dari main_socketio_update.py bagian @app.route('/admin/stock-monitor')
    pass

@app.route('/admin/update-stock', methods=['POST'])
@login_required
def update_stock():
    # ... paste code dari main_socketio_update.py bagian @app.route('/admin/update-stock')
    pass



@app.route('/transaction/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Hapus transaksi dan kembalikan stock"""
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'message': 'Login dulu'}), 401
    
    try:
        db = get_db()
        cursor = db.cursor()
        
        # Cek transaksi ada atau tidak
        cursor.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
        trx = cursor.fetchone()
        
        if not trx:
            return jsonify({'success': False, 'message': 'Transaksi tidak ditemukan'}), 404
        
        # Ambil items dari transaksi
        cursor.execute('SELECT product_id, quantity FROM transaction_items WHERE transaction_id = ?', (transaction_id,))
        items = cursor.fetchall()
        
        # Kembalikan stock untuk setiap item
        for item in items:
            cursor.execute('UPDATE products SET stock = stock + ? WHERE id = ?', 
                          (item['quantity'], item['product_id']))
        
        # Hapus items
        cursor.execute('DELETE FROM transaction_items WHERE transaction_id = ?', (transaction_id,))
        
        # Hapus transaction
        cursor.execute('DELETE FROM transactions WHERE id = ?', (transaction_id,))
        
        db.commit()
        db.close()
        
        return jsonify({'success': True, 'message': f'Transaksi #{transaction_id} berhasil dihapus'}), 200
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
