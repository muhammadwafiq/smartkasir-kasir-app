/**
 * Barcode Scanner Handler
 * Captures barcode input dan auto-add produk ke cart
 */

let scannerBuffer = '';
let scannerTimeout = null;
const SCANNER_TIMEOUT = 100; // ms

// Auto-focus scanner input on load
window.addEventListener('load', () => {
    console.log('🔍 Scanner initialized - ready to scan');
    focusScanner();
    setupScannerListener();
});

function focusScanner() {
    const scannerInput = document.getElementById('barcode-input');
    if (scannerInput) {
        scannerInput.focus();
    }
}

function setupScannerListener() {
    const scannerInput = document.getElementById('barcode-input');
    
    scannerInput.addEventListener('input', (e) => {
        const value = e.target.value.trim();
        
        // Deteksi barcode (Enter key akan trigger ini)
        if (value && (value.length > 5 || e.key === 'Enter')) {
            handleBarcodeScanned(value);
            scannerInput.value = ''; // Clear input
            focusScanner(); // Re-focus
        }
    });
    
    // Listen for keyboard input
    scannerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            const barcode = scannerInput.value.trim();
            if (barcode) {
                handleBarcodeScanned(barcode);
                scannerInput.value = '';
                focusScanner();
            }
        }
    });
}

async function handleBarcodeScanned(barcode) {
    console.log('📲 Barcode scanned:', barcode);
    
    try {
        // Fetch product by barcode/ID
        const response = await fetch('/api/product/barcode', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ barcode: barcode })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            const product = data.product;
            console.log('✅ Found product:', product.name);
            
            // Check stock
            if (product.stock <= 0) {
                showErrorNotification(`❌ ${product.name} - Stok habis!`);
                return;
            }
            
            // Add to cart
            addToCart(product.id, 1);
            showScannerNotification(`✅ ${product.name} ditambahkan`);
        } else {
            showErrorNotification(`❌ Produk tidak ditemukan: ${barcode}`);
        }
    } catch (error) {
        console.error('Error scanning barcode:', error);
        showErrorNotification('❌ Error saat scan barcode');
    }
}

function showScannerNotification(message) {
    const notif = document.getElementById('scanner-notification');
    const text = document.getElementById('notification-text');
    
    text.textContent = message;
    notif.style.display = 'block';
    
    // Auto-hide after 2 seconds
    setTimeout(() => {
        notif.style.display = 'none';
    }, 2000);
}

function showErrorNotification(message) {
    const notif = document.getElementById('error-notification');
    const text = document.getElementById('error-text');
    
    text.textContent = message;
    notif.style.display = 'block';
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        notif.style.display = 'none';
    }, 3000);
}

// Keep scanner focused even if user clicks elsewhere
document.addEventListener('click', (e) => {
    // Jangan focus ke scanner kalau click on buttons atau inputs
    if (e.target.tagName !== 'BUTTON' && 
        e.target.tagName !== 'INPUT' || 
        e.target.id === 'barcode-input') {
        focusScanner();
    }
});

// Auto-focus scanner saat page load
document.addEventListener('DOMContentLoaded', focusScanner);
