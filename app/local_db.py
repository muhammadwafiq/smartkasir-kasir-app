import sqlite3
import json
from datetime import datetime

DB_FILE = "kasir.db"

def init_db():
    """Initialize local SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER,
            total_amount REAL,
            payment_method TEXT,
            notes TEXT,
            items_json TEXT,
            synced INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            category TEXT,
            price REAL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Local database initialized!")

def save_transaction(total_amount, payment_method, items, notes=""):
    """Save transaction to local DB"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    items_json = json.dumps(items)
    
    cursor.execute('''
        INSERT INTO transactions (total_amount, payment_method, items_json, notes, synced)
        VALUES (?, ?, ?, ?, 0)
    ''', (total_amount, payment_method, items_json, notes))
    
    conn.commit()
    trans_id = cursor.lastrowid
    conn.close()
    
    return trans_id

def get_today_transactions():
    """Get all transactions today"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, total_amount, payment_method, notes, created_at
        FROM transactions
        WHERE DATE(created_at) = DATE('now')
        ORDER BY created_at DESC
    ''')
    
    transactions = cursor.fetchall()
    conn.close()
    
    return transactions

def get_transaction_detail(trans_id):
    """Get transaction detail"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, total_amount, payment_method, notes, items_json, created_at
        FROM transactions
        WHERE id = ?
    ''', (trans_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        items = json.loads(result[4])
        return {
            "id": result[0],
            "total_amount": result[1],
            "payment_method": result[2],
            "notes": result[3],
            "items": items,
            "created_at": result[5]
        }
    
    return None

def get_all_products():
    """Get all products from local DB"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name, category, price FROM products ORDER BY category, name')
    
    products = []
    for row in cursor.fetchall():
        products.append({
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "price": row[3]
        })
    
    conn.close()
    return products

def get_products_by_category(category):
    """Get products by category"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, category, price
        FROM products
        WHERE category = ?
        ORDER BY name
    ''', (category,))
    
    products = []
    for row in cursor.fetchall():
        products.append({
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "price": row[3]
        })
    
    conn.close()
    return products

def get_categories():
    """Get all unique categories"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT category FROM products ORDER BY category')
    
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return categories

def get_today_summary():
    """Get today's sales summary"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_transactions,
            SUM(total_amount) as total_revenue
        FROM transactions
        WHERE DATE(created_at) = DATE('now')
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    if result and result[1]:
        return {
            "total_transactions": result[0],
            "total_revenue": result[1]
        }
    
    return {"total_transactions": 0, "total_revenue": 0}

def save_products(products):
    """Save products from server to local"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM products')
    
    for product in products:
        cursor.execute('''
            INSERT INTO products (id, name, category, price)
            VALUES (?, ?, ?, ?)
        ''', (product['id'], product['name'], product['category'], product['price']))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()

def get_product_by_barcode_local(barcode):
    """Get product by barcode from local database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, price, barcode 
        FROM products 
        WHERE barcode = ? OR id = CAST(? AS INTEGER)
        LIMIT 1
    ''', (barcode, barcode if barcode.isdigit() else '0'))
    
    product = cursor.fetchone()
    conn.close()
    
    if product:
        return {
            "id": product[0],
            "name": product[1],
            "price": product[2],
            "barcode": product[3]
        }
    return None
