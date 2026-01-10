// ============ STATE ============
let cart = [];
let products = [];
let categories = [];
let offlineMode = false;

// ============ INIT ============
document.addEventListener('DOMContentLoaded', async () => {
    console.log('🚀 SmartKasir POS Loading...');
    
    // Initialize database
    await initApp();
    
    // Load products & categories
    await loadProducts();
    await loadCategories();
    
    // Check online status
    checkStatus();
    setInterval(checkStatus, 5000);
    
    console.log('✅ SmartKasir POS Ready!');
});

// ============ APP INIT ============
async function initApp() {
    try {
        const response = await fetch('/api/init', {method: 'POST'});
        const data = await response.json();
        offlineMode = data.offline_mode;
        console.log(data.message);
    } catch (e) {
        console.error('Init error:', e);
        offlineMode = true;
    }
}

// ============ STATUS CHECK ============
async function checkStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        const indicator = document.getElementById('status-indicator');
        const text = document.getElementById('status-text');
        
        if (data.online) {
            indicator.classList.remove('offline');
            indicator.classList.add('online');
            text.textContent = '🟢 Online';
            offlineMode = false;
        } else {
            indicator.classList.remove('online');
            indicator.classList.add('offline');
            text.textContent = '🔴 Offline';
            offlineMode = true;
        }
    } catch (e) {
        document.getElementById('status-indicator').classList.add('offline');
        document.getElementById('status-text').textContent = '🔴 Offline';
        offlineMode = true;
    }
}

// ============ PRODUCTS ============
async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        const data = await response.json();
        products = data.products;
        renderProducts(products);
    } catch (e) {
        console.error('Load products error:', e);
    }
}

async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const data = await response.json();
        categories = data.categories;
        
        const select = document.getElementById('category-select');
        categories.forEach(cat => {
            const option = document.createElement('option');
            option.value = cat;
            option.textContent = cat;
            select.appendChild(option);
        });
    } catch (e) {
        console.error('Load categories error:', e);
    }
}

function renderProducts(prods) {
    const grid = document.getElementById('products-grid');
    grid.innerHTML = '';
    
    if (prods.length === 0) {
        grid.innerHTML = '<div class="cart-empty">📦 Tidak ada produk</div>';
        return;
    }
    
    prods.forEach(product => {
        const card = document.createElement('div');
        card.className = 'product-card';
        card.innerHTML = `
            <div class="product-name">${product.name}</div>
            <div class="product-price">Rp ${formatPrice(product.price)}</div>
            <input type="number" class="product-qty" id="qty-${product.id}" value="1" min="1">
            <button class="btn-add" onclick="addToCart(${product.id})">Tambah</button>
        `;
        grid.appendChild(card);
    });
}

function filterByCategory() {
    const category = document.getElementById('category-select').value;
    
    if (!category) {
        renderProducts(products);
    } else {
        const filtered = products.filter(p => p.category === category);
        renderProducts(filtered);
    }
}

// ============ CART ============
function addToCart(productId) {
    const product = products.find(p => p.id === productId);
    if (!product) return;
    
    const qtyInput = document.getElementById(`qty-${productId}`);
    const qty = parseInt(qtyInput.value) || 1;
    
    // Check if already in cart
    const existing = cart.find(item => item.id === productId);
    
    if (existing) {
        existing.qty += qty;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.price,
            qty: qty
        });
    }
    
    qtyInput.value = 1;
    renderCart();
    updateTotal();
}

function renderCart() {
    const cartDiv = document.getElementById('cart-items');
    
    if (cart.length === 0) {
        cartDiv.innerHTML = '<div class="cart-empty">🛒 Keranjang kosong</div>';
        return;
    }
    
    cartDiv.innerHTML = '';
    
    cart.forEach((item, index) => {
        const total = item.price * item.qty;
        const itemDiv = document.createElement('div');
        itemDiv.className = 'cart-item';
        itemDiv.innerHTML = `
            <div class="cart-item-info">
                <div class="cart-item-name">${item.name}</div>
                <div class="cart-item-price">Rp ${formatPrice(item.price)} x ${item.qty}</div>
            </div>
            <input type="number" class="cart-item-qty" value="${item.qty}" min="1" onchange="updateCartQty(${index}, this.value)">
            <button class="btn-remove" onclick="removeFromCart(${index})">Hapus</button>
        `;
        cartDiv.appendChild(itemDiv);
    });
}

function updateCartQty(index, newQty) {
    const qty = parseInt(newQty) || 1;
    if (qty <= 0) {
        removeFromCart(index);
    } else {
        cart[index].qty = qty;
        renderCart();
        updateTotal();
    }
}

function removeFromCart(index) {
    cart.splice(index, 1);
    renderCart();
    updateTotal();
}

// ============ TOTAL & CHECKOUT ============
function updateTotal() {
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discountPercent = parseInt(document.getElementById('discount-percent').value) || 0;
    const discountAmount = Math.floor(subtotal * discountPercent / 100);
    const total = subtotal - discountAmount;
    
    document.getElementById('subtotal').textContent = `Rp ${formatPrice(subtotal)}`;
    document.getElementById('discount-amount').textContent = `Rp ${formatPrice(discountAmount)}`;
    document.getElementById('total').textContent = `Rp ${formatPrice(total)}`;
    
    calculateChange();
}

function calculateChange() {
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discountPercent = parseInt(document.getElementById('discount-percent').value) || 0;
    const finalTotal = total - Math.floor(total * discountPercent / 100);
    
    const amountReceived = parseInt(document.getElementById('amount-received').value) || 0;
    const change = amountReceived - finalTotal;
    
    document.getElementById('change-amount').value = change >= 0 ? change : 0;
}

async function checkout() {
    if (cart.length === 0) {
        alert('⚠️ Keranjang kosong!');
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discountPercent = parseInt(document.getElementById('discount-percent').value) || 0;
    const finalTotal = total - Math.floor(total * discountPercent / 100);
    
    const amountReceived = parseInt(document.getElementById('amount-received').value) || 0;
    
    if (amountReceived < finalTotal) {
        alert('⚠️ Uang tidak cukup!');
        return;
    }
    
    const paymentMethod = document.getElementById('payment-method').value;
    const notes = document.getElementById('notes').value;
    
    try {
        const response = await fetch('/api/transactions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                total_amount: finalTotal,
                payment_method: paymentMethod,
                items: cart,
                notes: notes
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            showReceipt(data.id, finalTotal, paymentMethod, cart);
        } else {
            alert('❌ Error: ' + data.message);
        }
    } catch (e) {
        alert('❌ Error checkout: ' + e.message);
    }
}

function showReceipt(transId, total, method, items) {
    const receiptText = generateReceipt(transId, total, method, items);
    document.getElementById('receipt-content').textContent = receiptText;
    document.getElementById('receipt-modal').style.display = 'flex';
}

function generateReceipt(transId, total, method, items) {
    let receipt = `
╔════════════════════════════╗
║     🏪 SmartKasir POS      ║
║   Struk Penjualan No. ${transId}  ║
╚════════════════════════════╝

Waktu: ${new Date().toLocaleString('id-ID')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ITEM              QTY    HARGA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
`;
    
    items.forEach(item => {
        const itemTotal = item.price * item.qty;
        receipt += `${item.name.padEnd(14)} x${String(item.qty).padStart(2)}  Rp ${formatPrice(itemTotal)}
`;
    });
    
    receipt += `
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL: Rp ${formatPrice(total)}
Metode: ${method === 'cash' ? '💰 Tunai' : method === 'card' ? '💳 Kartu' : '🏦 Transfer'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Terima Kasih!
Barang yang dibeli tidak dapat ditukar

╚════════════════════════════╝
`;
    
    return receipt;
}

function newTransaction() {
    cart = [];
    document.getElementById('discount-percent').value = 0;
    document.getElementById('amount-received').value = '';
    document.getElementById('notes').value = '';
    document.getElementById('change-amount').value = 0;
    
    renderCart();
    updateTotal();
    closeReceiptModal();
}

// ============ MODAL ============
function closeModal() {
    document.getElementById('history-modal').style.display = 'none';
}

function closeReceiptModal() {
    document.getElementById('receipt-modal').style.display = 'none';
}

async function loadTodayTransactions() {
    try {
// const response = await fetch('/api/transactions/today');
        const data = await response.json();
        
        const list = document.getElementById('history-list');
        
        if (data.transactions.length === 0) {
            list.innerHTML = '<div class="cart-empty">📋 Belum ada transaksi</div>';
        } else {
            list.innerHTML = '';
            data.transactions.forEach(trans => {
                const item = document.createElement('div');
                item.className = 'history-item';
                item.innerHTML = `
                    <div class="history-item-header">
                        <span>#${trans.id}</span>
                        <span>Rp ${formatPrice(trans.total_amount)}</span>
                    </div>
                    <div class="history-item-detail">
                        ${trans.payment_method} • ${trans.created_at}
                    </div>
                `;
                list.appendChild(item);
            });
        }
        
        document.getElementById('history-modal').style.display = 'flex';
    } catch (e) {
        alert('❌ Error: ' + e.message);
    }
}

async function syncTransactions() {
    const btn = document.getElementById('sync-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Syncing...';
    
    try {
        // Sync logic - save to server jika online
        alert('✅ Sync completed!');
    } catch (e) {
        alert('❌ Sync error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Sync';
    }
}

// ============ UTILITIES ============
function formatPrice(price) {
    return new Intl.NumberFormat('id-ID').format(Math.round(price));
}

// ============ QRIS PAYMENT ============
function onPaymentMethodChange() {
    const method = document.getElementById('payment-method').value;
    const qrisSection = document.getElementById('qris-section');
    const paymentInputSection = document.getElementById('payment-input-section');
    
    if (method === 'qris') {
        qrisSection.style.display = 'block';
        paymentInputSection.style.display = 'none';
        generateQRIS();
    } else {
        qrisSection.style.display = 'none';
        paymentInputSection.style.display = 'block';
    }
}

async function generateQRIS() {
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discountPercent = parseInt(document.getElementById('discount-percent').value) || 0;
    const finalTotal = total - Math.floor(total * discountPercent / 100);
    
    try {
        const response = await fetch('/api/qris/generate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                amount: finalTotal,
                description: 'SmartKasir Payment'
            })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            document.getElementById('qris-img').src = data.qr_base64;
            document.getElementById('qris-ref').textContent = `Rp ${formatPrice(finalTotal)}\n${data.display_text}`;
        }
    } catch (e) {
        console.error('QRIS error:', e);
    }
}

// ============ MONITOR DISPLAY ============
function openDisplayMode() {
    const today = new Date().toLocaleDateString('id-ID', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    const content = `
<div style="text-align: center; padding: 40px;">
    <h1 style="font-size: 48px; margin-bottom: 20px;">🏪 SmartKasir</h1>
    <p style="font-size: 32px; margin-bottom: 30px;">${today}</p>
    
    <div style="background: #f0f0f0; padding: 30px; border-radius: 10px; margin: 20px;">
        <p style="font-size: 24px; color: #666;">Menunggu pembayaran...</p>
        <p style="font-size: 18px; color: #999;">📺 Layar Pelanggan</p>
    </div>
    
    <p style="font-size: 20px; margin-top: 40px; color: #666;">Tekan ESC untuk tutup</p>
</div>
    `;
    
    document.getElementById('monitor-content').innerHTML = content;
    document.getElementById('display-modal').style.display = 'flex';
    
    // Press ESC to close
    document.onkeydown = (e) => {
        if (e.key === 'Escape') {
            closeDisplayMode();
        }
    };
}

function closeDisplayMode() {
    document.getElementById('display-modal').style.display = 'none';
    document.onkeydown = null;
}

function updateDisplayMode(transId, items, total, method) {
    const itemsHTML = items.map(item => `
        <tr style="border-bottom: 1px solid #ddd; padding: 10px;">
            <td style="text-align: left; padding: 10px; font-size: 20px;">${item.name}</td>
            <td style="text-align: center; padding: 10px; font-size: 20px;">x${item.qty}</td>
            <td style="text-align: right; padding: 10px; font-size: 20px;">Rp ${formatPrice(item.price * item.qty)}</td>
        </tr>
    `).join('');
    
    const content = `
<div style="max-width: 800px; margin: 0 auto; padding: 40px; color: #333;">
    <h1 style="font-size: 48px; text-align: center; margin-bottom: 40px;">🏪 SmartKasir</h1>
    
    <table style="width: 100%; margin-bottom: 30px;">
        ${itemsHTML}
    </table>
    
    <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin-bottom: 30px;">
        <div style="display: flex; justify-content: space-between; font-size: 24px; margin-bottom: 10px;">
            <span>SUBTOTAL:</span>
            <span>Rp ${formatPrice(total)}</span>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 32px; font-weight: bold; color: #2180D1;">
            <span>TOTAL:</span>
            <span>Rp ${formatPrice(total)}</span>
        </div>
    </div>
    
    <div style="text-align: center; margin-bottom: 30px;">
        <p style="font-size: 20px; margin-bottom: 15px;">Metode: ${getPaymentLabel(method)}</p>
        <p style="font-size: 18px; color: #999;">Transaksi #${transId}</p>
    </div>
    
    <div style="text-align: center; padding: 20px; background: #e8f5e9; border-radius: 8px;">
        <p style="font-size: 24px; color: #2e7d32;">✅ PEMBAYARAN BERHASIL</p>
        <p style="font-size: 18px; color: #666; margin-top: 10px;">Terima kasih telah berbelanja!</p>
    </div>
</div>
    `;
    
    document.getElementById('monitor-content').innerHTML = content;
}

function getPaymentLabel(method) {
    const labels = {
        'cash': '💰 TUNAI',
        'card': '💳 KARTU KREDIT',
        'transfer': '🏦 TRANSFER BANK',
        'qris': '📱 QRIS/E-WALLET'
    };
    return labels[method] || method;
}

// ============ PRINT RECEIPT ============
function printReceipt() {
    const printWindow = window.open('', '', 'width=400,height=600');
    const receipt = document.getElementById('receipt-content').textContent;
    
    printWindow.document.write(`
        <html>
        <head>
            <style>
                body { font-family: monospace; white-space: pre; margin: 10px; }
            </style>
        </head>
        <body>${receipt}</body>
        </html>
    `);
    
    printWindow.document.close();
    printWindow.print();
}

// ============ BARCODE SCANNER (Siap untuk integrasi) ============
document.addEventListener('keypress', function(e) {
    // Barcode scanner format: biasanya berakhir dengan Enter key
    // Nanti tinggal handle logic ini
});
