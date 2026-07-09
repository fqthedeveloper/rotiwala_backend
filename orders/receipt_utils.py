# orders/receipt_utils.py
from decimal import Decimal
from datetime import datetime
from django.utils import timezone
from django.conf import settings
import qrcode
from io import BytesIO
import base64
# orders/receipt_utils.py
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

# orders/receipt_utils.py
from decimal import Decimal
from datetime import datetime
from django.utils import timezone

def generate_receipt_text(order):
    """
    Generate formatted receipt text for thermal printer
    """
    line = '=' * 40
    dashed = '-' * 40
    
    # Get order items
    items = order.items.all()
    
    # Build receipt
    receipt_lines = []
    receipt_lines.append(line)
    receipt_lines.append('          ROTI WALA')
    receipt_lines.append(line)
    receipt_lines.append(f'Order No :')
    receipt_lines.append(f'{order.order_number}')
    receipt_lines.append('')
    receipt_lines.append(f'Date')
    receipt_lines.append(order.ordered_at.strftime('%d-%b-%Y') if order.ordered_at else timezone.now().strftime('%d-%b-%Y'))
    receipt_lines.append('')
    receipt_lines.append(f'Customer')
    receipt_lines.append(order.customer_name or 'Walk-in Customer')
    receipt_lines.append('')
    receipt_lines.append(f'Phone')
    receipt_lines.append(order.customer_phone or 'N/A')
    receipt_lines.append('')
    receipt_lines.append(dashed)
    receipt_lines.append('')
    
    # Items with proper alignment
    for item in items:
        qty = item.quantity
        # Use original_price for display, fallback to final_price or total_price
        price_per_item = float(item.original_price) if item.original_price else float(item.final_price or item.total_price / item.quantity)
        name = item.item_name[:25].ljust(25)  # Limit name length
        total_price = float(item.total_price)
        price_display = f"₹{total_price:.2f}".rjust(10)
        receipt_lines.append(f'{qty} x {name} {price_display}')
    
    receipt_lines.append('')
    receipt_lines.append(dashed)
    receipt_lines.append('')
    
    # Totals
    original_amount = float(order.original_amount or order.total_amount)
    receipt_lines.append(f'Subtotal              ₹{original_amount:.2f}')
    
    if order.discount_amount and float(order.discount_amount) > 0:
        receipt_lines.append(f'Discount              ₹-{float(order.discount_amount):.2f}')
    
    receipt_lines.append('')
    receipt_lines.append(f'Grand Total           ₹{float(order.total_amount):.2f}')
    
    # Payment info
    receipt_lines.append('')
    receipt_lines.append(f'Payment: {order.payment_method.upper()}')
    receipt_lines.append(f'Status: {order.payment_status.upper()}')
    
    if order.order_type == 'walkin':
        receipt_lines.append(f'Type: WALK-IN')
    else:
        receipt_lines.append(f'Type: ONLINE')
    
    receipt_lines.append('')
    receipt_lines.append(line)
    receipt_lines.append('Thank You Visit Again')
    receipt_lines.append(line)
    
    return '\n'.join(receipt_lines)


def generate_receipt_data(order):
    """
    Generate structured receipt data for frontend
    """
    items_data = []
    for item in order.items.all():
        # Get the price per item
        if item.original_price:
            price_per_item = float(item.original_price)
        elif item.final_price:
            price_per_item = float(item.final_price)
        else:
            price_per_item = float(item.total_price / item.quantity) if item.quantity > 0 else 0
        
        items_data.append({
            'name': item.item_name,
            'quantity': item.quantity,
            'price': price_per_item,
            'total': float(item.total_price),
            'discount_amount': float(item.discount_amount) if item.discount_amount else 0,
            'final_price': float(item.final_price) if item.final_price else float(item.total_price),
            'original_price': float(item.original_price) if item.original_price else float(item.total_price),
        })
    
    return {
        'order_number': order.order_number,
        'order_id': str(order.id),
        'ordered_at': order.ordered_at.strftime('%d-%b-%Y %I:%M %p') if order.ordered_at else timezone.now().strftime('%d-%b-%Y %I:%M %p'),
        'customer_name': order.customer_name or 'Walk-in Customer',
        'customer_phone': order.customer_phone or 'N/A',
        'items': items_data,
        'original_amount': float(order.original_amount or order.total_amount),
        'discount_amount': float(order.discount_amount or 0),
        'total_amount': float(order.total_amount),
        'payment_method': order.payment_method,
        'payment_status': order.payment_status,
        'order_type': order.order_type,
        'shop_name': order.shop.name if order.shop else 'ROTI WALA',
        'receipt_text': generate_receipt_text(order),
    }

def generate_qr_code(order):
    """
    Generate QR code for order (optional - for digital receipts)
    """
    qr_data = f"ORDER:{order.order_number}|AMOUNT:{order.total_amount}|DATE:{order.ordered_at}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str