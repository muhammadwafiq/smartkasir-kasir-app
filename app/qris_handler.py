import qrcode
import json
from datetime import datetime
import base64
from io import BytesIO

class QRISGenerator:
    """Generate QRIS (Quick Response Indonesian Standard) untuk pembayaran"""
    
    def __init__(self, merchant_name="SmartKasir", merchant_id="ID123456"):
        self.merchant_name = merchant_name
        self.merchant_id = merchant_id
    
    def generate_qris(self, amount, trans_id, notes=""):
        """
        Generate QRIS QR Code untuk pembayaran
        Format: static QR dengan embedded amount
        """
        
        # QRIS Format (EMV Format - simplified untuk demo)
        # Format: MerchantID | Amount | Transaction ID | Notes
        qris_data = {
            "merchant": self.merchant_id,
            "amount": int(amount),
            "ref": f"TRX{trans_id:05d}",
            "desc": notes or self.merchant_name,
            "timestamp": datetime.now().isoformat()
        }
        
        qris_string = json.dumps(qris_data)
        
        # Generate QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(qris_string)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert ke base64 untuk display di web
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            "qr_base64": f"data:image/png;base64,{img_str}",
            "qris_data": qris_data,
            "display_text": f"Rp {amount:,}\nRef: TRX{trans_id:05d}"
        }
    
    def generate_receipt_with_qris(self, trans_id, items, total, method, qris_code=None):
        """Generate struk dengan QRIS"""
        
        receipt = f"""
╔══════════════════════════════════╗
║     🏪 SmartKasir POS            ║
║   BUKTI PEMBAYARAN No. {trans_id:05d}  ║
╚══════════════════════════════════╝

Waktu: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
═══════════════════════════════════

ITEM                    QTY   HARGA
───────────────────────────────────
"""
        
        for item in items:
            item_total = item['price'] * item['qty']
            receipt += f"{item['name'][:20].ljust(20)} x{str(item['qty']).rjust(2)}  Rp {item_total:>8,}\n"
        
        receipt += f"""
═══════════════════════════════════
TOTAL: Rp {total:,}
Metode: {self._get_payment_label(method)}
═══════════════════════════════════
"""
        
        if method == "qris":
            receipt += f"""
📱 SCAN KODE QRIS DI BAWAH
Referensi: TRX{trans_id:05d}

[QR CODE AREA]

💡 Scan dengan aplikasi pembayaran
   GCash, OVO, GoPay, DANA, dll
"""
        
        receipt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Terima Kasih Telah Berbelanja!
   Barang sudah dibeli tidak dapat ditukar

👍 Follow media sosial kami untuk promo
📞 Customer Service: 021-XXXX-XXXX

╚══════════════════════════════════╝
"""
        
        return receipt
    
    @staticmethod
    def _get_payment_label(method):
        labels = {
            "cash": "💰 TUNAI",
            "card": "💳 KARTU KREDIT",
            "transfer": "🏦 TRANSFER BANK",
            "qris": "📱 QRIS/E-WALLET"
        }
        return labels.get(method, method.upper())

# Test
if __name__ == "__main__":
    qris = QRISGenerator()
    result = qris.generate_qris(50000, 1, "Order Makanan")
    print("✅ QRIS Generated!")
    print(f"Display: {result['display_text']}")
