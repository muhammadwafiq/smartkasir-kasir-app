
def get_product_by_barcode_local(barcode):
    """Get product by barcode from local database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, price, stock, barcode 
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
            "stock": product[3],
            "barcode": product[4]
        }
    return None
