from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import date
from datetime import datetime
import sqlite3
from threading import local

# Thread-local storage untuk database connections
_thread_local = local()

def get_db():
    """Get database connection for current thread"""
    db = sqlite3.connect('kasir.db')
    db.row_factory = sqlite3.Row
    return db


app = Flask(__name__)
CORS(app)

DATABASE = 'kasir.db'

def get_db():
    """Get database connection"""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db

db = get_db()

# ============================================
# INITIALIZE DATABASE SCHEMA
# ============================================

def init_db():
    """Initialize database tables"""
    db_conn = get_db()
    cursor = db_conn.cursor()
    
    # Products table (existing)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT,
            price INTEGER NOT NULL,
            barcode TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Transactions table (NEW)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            items_json TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            payment_status TEXT DEFAULT 'completed',
            kasir_name TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Transaction items detail (NEW)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transaction_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price_per_unit INTEGER NOT NULL,
            subtotal INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    
    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transaction_date ON transactions(transaction_date)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_transaction_status ON transactions(payment_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_product_barcode ON products(barcode)')
    
    db_conn.commit()
    print("✅ Database schema initialized")

init_db()

# ============================================
# PRODUCT ENDPOINTS (Existing)
# ============================================

@app.route('/api/product/barcode', methods=['POST'])
def get_product_by_barcode():
    """Get product by barcode"""
    try:
        data = request.get_json()
        barcode = data.get('barcode', '')
        
        if not barcode:
            return jsonify({'error': 'Barcode required'}), 400
        db_conn = get_db()
        cursor = db_conn.cursor()
        
        cursor.execute('SELECT id, name, price, barcode FROM products WHERE barcode = ?', (barcode,))
        product = cursor.fetchone()
        db_conn.close()
        

        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        return jsonify({
            'id': product['id'],
            'name': product['name'],
            'price': product['price'],
            'barcode': product['barcode']
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/products', methods=['GET'])
def get_all_products():
    """Get all products"""
    try:
        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute('SELECT id, name, category, price, barcode FROM products ORDER BY name')
        products = cursor.fetchall()
        
        products_list = [dict(p) for p in products]
        return jsonify({'success': True, 'data': products_list}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# TRANSACTION ENDPOINTS (NEW)
# ============================================

@app.route('/api/transactions/save', methods=['POST'])
def save_transaction():
    """
    Save complete transaction ke database.
    
    Request JSON:
    {
      "items": [
        {"id": 1, "name": "Mie Goreng", "qty": 2, "price": 3000, "subtotal": 6000},
        {"id": 2, "name": "Teh Botol", "qty": 1, "price": 5000, "subtotal": 5000}
      ],
      "total": 11000,
      "payment_method": "QRIS" atau "Tunai",
      "kasir_name": "Wafiq" (optional)
    }
    """
    try:
        data = request.get_json()
        
        # Validasi input
        if not data or 'items' not in data or 'total' not in data:
            return jsonify({'error': 'Invalid data: items and total required'}), 400
        
        items = data.get('items', [])
        total = data.get('total', 0)
        payment_method = data.get('payment_method', 'Tunai')
        kasir_name = data.get('kasir_name', 'Unknown')
        notes = data.get('notes', '')
        
        if total <= 0:
            return jsonify({'error': 'Total must be greater than 0'}), 400
        
        db_conn = get_db()
        cursor = db_conn.cursor()
        
        # Insert ke transactions table
        cursor.execute('''
            INSERT INTO transactions (items_json, total_amount, payment_method, kasir_name, notes, payment_status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (json.dumps(items), total, payment_method, kasir_name, notes, 'completed'))
        
        transaction_id = cursor.lastrowid
        
        # Insert detail items ke transaction_items table
        for item in items:
            cursor.execute('''
                INSERT INTO transaction_items (transaction_id, product_id, product_name, quantity, price_per_unit, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                transaction_id,
                item.get('id', 0),
                item.get('name', ''),
                item.get('qty', 1),
                item.get('price', 0),
                item.get('subtotal', 0)
            ))
        
        db_conn.commit()
        
        return jsonify({
            'success': True,
            'message': f'Transaction {transaction_id} saved successfully',
            'transaction_id': transaction_id
        }), 201
        
    except Exception as e:
        db_conn.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    """
    Get transaction history with optional filtering.
    
    Query params:
    - limit: jumlah records (default: 50)
    - offset: pagination (default: 0)
    - date_from: filter tanggal mulai (YYYY-MM-DD)
    - date_to: filter tanggal akhir (YYYY-MM-DD)
    - payment_method: filter metode pembayaran
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        payment_method = request.args.get('payment_method')
        
        query = 'SELECT * FROM transactions WHERE 1=1'
        params = []
        
        # Apply filters
        if date_from:
            query += ' AND DATE(transaction_date) >= ?'
            params.append(date_from)
        if date_to:
            query += ' AND DATE(transaction_date) <= ?'
            params.append(date_to)
        if payment_method:
            query += ' AND payment_method = ?'
            params.append(payment_method)
        
        query += ' ORDER BY transaction_date DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        # Convert to dict
        transactions_list = []
        for row in transactions:
            transactions_list.append({
                'id': row['id'],
                'transaction_date': row['transaction_date'],
                'items': json.loads(row['items_json']),
                'total_amount': row['total_amount'],
                'payment_method': row['payment_method'],
                'payment_status': row['payment_status'],
                'kasir_name': row['kasir_name'],
                'notes': row['notes']
            })
        
        return jsonify({
            'success': True,
            'data': transactions_list,
            'count': len(transactions_list)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/summary', methods=['GET'])
def get_today_summary():
    """
    Get ringkasan penjualan hari ini.
    Return: total transaksi, total revenue, jumlah items terjual
    """
    try:
        db_conn = get_db()
        cursor = db_conn.cursor()
        
        # Total transaksi hari ini
        cursor.execute('''
            SELECT 
                COUNT(*) as total_transactions,
                COALESCE(SUM(total_amount), 0) as total_revenue
            FROM transactions
            WHERE DATE(transaction_date) = DATE('now')
        ''')
        
        result = cursor.fetchone()
        
        # By payment method
        cursor.execute('''
            SELECT 
                payment_method,
                COUNT(*) as count,
                COALESCE(SUM(total_amount), 0) as revenue
            FROM transactions
            WHERE DATE(transaction_date) = DATE('now')
            GROUP BY payment_method
        ''')
        
        by_method = cursor.fetchall()
        
        summary = {
            'date': date.today().isoformat(),
            'total_transactions': result['total_transactions'],
            'total_revenue': result['total_revenue'],
            'by_method': [dict(m) for m in by_method]
        }
        
        return jsonify({
            'success': True,
            'data': summary
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transactions/<int:transaction_id>', methods=['GET'])
def get_transaction_detail(transaction_id):
    """Get detail transaksi by ID"""
    try:
        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute('SELECT * FROM transactions WHERE id = ?', (transaction_id,))
        transaction = cursor.fetchone()
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        return jsonify({
            'success': True,
            'data': {
                'id': transaction['id'],
                'transaction_date': transaction['transaction_date'],
                'items': json.loads(transaction['items_json']),
                'total_amount': transaction['total_amount'],
                'payment_method': transaction['payment_method'],
                'payment_status': transaction['payment_status'],
                'kasir_name': transaction['kasir_name'],
                'notes': transaction['notes']
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================
# MAIN PAGE
# ============================================
# ============================================
# CART OPERATIONS
# ============================================

# Session cart storage
cart_session = {}

@app.route('/add-to-cart/<barcode>', methods=['POST'])
def add_to_cart(barcode):
    """Tambah produk ke cart"""
    try:
        db_conn = get_db()
        cursor = db_conn.cursor()
        cursor.execute('SELECT * FROM products WHERE barcode = ?', (barcode,))
        product = cursor.fetchone()
        
        if not product:
            return jsonify({'success': False, 'message': 'Produk tidak ditemukan'}), 404
        
        if barcode in cart_session:
            cart_session[barcode]['qty'] += 1
        else:
            cart_session[barcode] = {
                'name': product['name'],
                'price': product['price'],
                'qty': 1
            }
        
        return jsonify({'success': True, 'cart': cart_session}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/update-qty/<barcode>/<int:change>', methods=['POST'])
def update_qty(barcode, change):
    """Update qty produk"""
    try:
        if barcode not in cart_session:
            return jsonify({'success': False, 'message': 'Produk tidak ada di cart'}), 404
        
        cart_session[barcode]['qty'] += change
        
        if cart_session[barcode]['qty'] <= 0:
            del cart_session[barcode]
        
        return jsonify({'success': True, 'cart': cart_session}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/remove-from-cart/<barcode>', methods=['POST'])
def remove_from_cart(barcode):
    """Hapus produk dari cart"""
    try:
        if barcode in cart_session:
            del cart_session[barcode]
        
        return jsonify({'success': True, 'cart': cart_session}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/checkout', methods=['POST'])
def checkout():
    """Process checkout"""
    try:
        data = request.get_json()
        payment_method = data.get('payment_method')
        nominal = data.get('nominal', 0)
        
        if not cart_session:
            return jsonify({'success': False, 'message': 'Keranjang kosong'}), 400
        
        # Hitung total
        total = sum(item['price'] * item['qty'] for item in cart_session.values())
        
        # Validasi nominal tunai
        if payment_method == 'tunai' and nominal < total:
            return jsonify({'success': False, 'message': 'Nominal kurang'}), 400
        
        # Save ke database
        db_conn = get_db()
        cursor = db_conn.cursor()
        
        items_json = json.dumps(cart_session)
        cursor.execute('''
            INSERT INTO transactions (items_json, total_amount, payment_method, payment_status, kasir_name)
            VALUES (?, ?, ?, ?, ?)
        ''', (items_json, total, payment_method, 'completed', 'Cashier'))
        
        db_conn.commit()
        invoice_number = cursor.lastrowid
        
        # Clear cart
        cart_session.clear()
        
        return jsonify({
            'success': True, 
            'invoice_number': invoice_number,
            'total': total
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
           app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
