// Replace checkout function dengan ini:
async function checkout() {
    if (cart.length === 0) {
        alert('⚠️ Keranjang kosong!');
        return;
    }
    
    const total = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discountPercent = parseInt(document.getElementById('discount-percent').value) || 0;
    const finalTotal = total - Math.floor(total * discountPercent / 100);
    const paymentMethod = document.getElementById('payment-method').value;
    const notes = document.getElementById('notes').value;
    
    // Validasi untuk non-QRIS
    if (paymentMethod !== 'qris') {
        const amountReceived = parseInt(document.getElementById('amount-received').value) || 0;
        if (amountReceived < finalTotal) {
            alert('⚠️ Uang tidak cukup!');
            return;
        }
    }
    
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
            // Show receipt
            showReceipt(data.id, finalTotal, paymentMethod, cart);
            
            // Update display monitor
            updateDisplayMode(data.id, cart, finalTotal, paymentMethod);
        } else {
            alert('❌ Error: ' + data.message);
        }
    } catch (e) {
        alert('❌ Error checkout: ' + e.message);
    }
}
