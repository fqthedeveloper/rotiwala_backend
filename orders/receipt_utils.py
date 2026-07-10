import os
import base64
from io import BytesIO
from django.utils import timezone

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Optional QR
try:
    import qrcode
    QR_SUPPORT = True
except ImportError:
    QR_SUPPORT = False

# ------------------------------------------------------------------
# Fonts – adjust path to match your project
# ------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_DIR = os.path.join(PROJECT_ROOT, 'fonts')

# Map style -> exact file name (as seen in your screenshot)
FONT_FILES = {
    '': 'DejaVuSans.ttf',
    'B': 'DejaVuSans-Bold.ttf',
    'I': 'DejaVuSans-Oblique.ttf',
    'BI': 'DejaVuSans-BoldOblique.ttf',
}

FONTS_AVAILABLE = all(os.path.exists(os.path.join(FONT_DIR, fname)) for fname in FONT_FILES.values())


def format_datetime_local(dt):
    if not dt:
        return timezone.now().strftime('%d-%b-%Y %I:%M %p')
    try:
        import pytz
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        local_tz = pytz.timezone('Asia/Kolkata')
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime('%d-%b-%Y %I:%M %p')
    except Exception:
        return dt.strftime('%d-%b-%Y %I:%M %p')


def generate_receipt_pdf(order, bill_type='standard'):
    """
    Generate a professional PDF invoice.  Always returns bytes.
    If fonts are missing, falls back to Helvetica with 'Rs.'.
    """
    if not PDF_SUPPORT:
        raise RuntimeError("fpdf2 not installed. Run: pip install fpdf2")

    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # ---------- Font family ----------
    if FONTS_AVAILABLE:
        for style, fname in FONT_FILES.items():
            font_path = os.path.join(FONT_DIR, fname)
            pdf.add_font('DejaVu', style=style, fname=font_path, uni=True)
        FONT_FAMILY = 'DejaVu'
        currency_symbol = '₹'
    else:
        FONT_FAMILY = 'Helvetica'
        currency_symbol = 'Rs.'

    def fmt(amount):
        try:
            return f"{currency_symbol} {amount:,.2f}"
        except Exception:
            return f"{currency_symbol} {amount:.2f}"

    # ---------- Metadata ----------
    pdf.set_title(f"Invoice - {order.order_number}")
    pdf.set_subject(f"Order {order.order_number} Receipt")
    pdf.set_author("ROTI WALA")
    pdf.set_creator("ROTI WALA POS")

    # ---------- Colors ----------
    brand_color = (230, 120, 40)   # orange
    dark_color = (40, 40, 40)
    light_gray = (245, 245, 245)

    # ---------- Header ----------
    pdf.set_text_color(*dark_color)
    pdf.set_font(FONT_FAMILY, 'B', 20)
    pdf.cell(0, 10, txt=(order.shop.name if getattr(order, 'shop', None) else 'ROTI WALA'), ln=1, align='C')

    pdf.set_font(FONT_FAMILY, '', 10)
    shop = getattr(order, 'shop', None)
    shop_lines = []
    if shop:
        if getattr(shop, 'address', None):
            shop_lines.append(shop.address)
        if getattr(shop, 'phone', None):
            shop_lines.append(f"Phone: {shop.phone}")
        if getattr(shop, 'email', None):
            shop_lines.append(f"Email: {shop.email}")
    shop_lines.append('Fresh Indian Breads & Curries')
    for line in shop_lines:
        pdf.cell(0, 5, txt=line, ln=1, align='C')

    pdf.ln(2)
    pdf.set_draw_color(*brand_color)
    pdf.set_line_width(0.7)
    y = pdf.get_y()
    pdf.line(15, y, 195, y)
    pdf.ln(4)

    # ---------- Invoice / Order Info ----------
    pdf.set_font(FONT_FAMILY, 'B', 12)
    pdf.cell(95, 6, txt=f"Invoice: {order.order_number}")
    pdf.set_font(FONT_FAMILY, '', 10)
    pdf.cell(95, 6, txt=f"Date: {format_datetime_local(order.ordered_at)}", ln=1, align='R')

    pdf.set_font(FONT_FAMILY, '', 10)
    pdf.cell(95, 6, txt=f"Customer: {order.customer_name or 'Walk-in Customer'}")
    pdf.cell(95, 6, txt=f"Phone: {order.customer_phone or 'N/A'}", ln=1, align='R')

    pdf.ln(2)

    # ---------- Items Table Header & Rows (requested columns) ----------
    # Columns requested:
    # 1 Description/Product
    # 2 Unit Price (single)
    # 3 Quantity
    # 4 Unit Total (unit_price * qty)
    # 5 Discount (per item total)  -- hide if no discounts present
    # 6 After Discount Amount

    # Build a list of item dicts first and detect discounts
    items = []
    has_discount = False
    for idx, item in enumerate(order.items.all(), start=1):
        qty = int(getattr(item, 'quantity', 0) or 0)
        name_raw = (getattr(item, 'item_name', '') or 'Item')
        line_subtotal = float(
            getattr(item, 'original_price', None) or
            getattr(item, 'final_price', None) or
            getattr(item, 'total_price', 0) or
            0
        )
        if qty > 0:
            unit_price = line_subtotal / qty
        else:
            unit_price = float(getattr(item, 'final_price', 0) or 0)
        unit_total = unit_price * qty
        discount_amt = float(getattr(item, 'discount_amount', 0) or 0)
        total = float(getattr(item, 'total_price', None) or getattr(item, 'final_price', None) or line_subtotal)
        if discount_amt > 0:
            has_discount = True
        items.append({
            'index': idx,
            'name': name_raw,
            'unit_price': unit_price,
            'quantity': qty,
            'unit_total': unit_total,
            'discount': discount_amt,
            'total': total,
        })

    # Column widths based on whether discount column is shown
    content_width = pdf.w - pdf.l_margin - pdf.r_margin
    if has_discount:
        # Include index column + description + unit + qty + unit total + discount + total
        col_widths = [12, 70, 25, 15, 25, 20, 25]
        headers = ['No.', 'Description', 'Unit', 'Qty', 'Unit Total', 'Discount', 'Total']
    else:
        # Include index column when no discount
        col_widths = [12, 85, 30, 20, 25, 25]  # No., Description, Unit, Qty, Unit Total, Total
        headers = ['No.', 'Description', 'Unit', 'Qty', 'Unit Total', 'Total']

    pdf.set_fill_color(*light_gray)
    pdf.set_font(FONT_FAMILY, 'B', 10)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 9, txt=h, border=1, align='C', fill=True)
    pdf.ln(9)

    # Rows
    pdf.set_font(FONT_FAMILY, '', 10)
    row_h = 8
    left_x = pdf.l_margin
    max_desc_len = 60
    for it in items:
        name_only = it['name']
        name = name_only if len(name_only) <= max_desc_len else name_only[: max_desc_len - 3] + '...'
        pdf.set_x(left_x)
        # render depending on columns (index column first)
        if has_discount:
            pdf.cell(col_widths[0], row_h, txt=str(it.get('index', '')), border=1, align='C')
            pdf.cell(col_widths[1], row_h, txt=name, border=1, align='L')
            pdf.cell(col_widths[2], row_h, txt=fmt(it['unit_price']), border=1, align='R')
            pdf.cell(col_widths[3], row_h, txt=str(it['quantity']), border=1, align='C')
            pdf.cell(col_widths[4], row_h, txt=fmt(it['unit_total']), border=1, align='R')
            pdf.cell(col_widths[5], row_h, txt=(f"-{fmt(it['discount'])}" if it['discount'] else ''), border=1, align='R')
            pdf.cell(col_widths[6], row_h, txt=fmt(it['total']), border=1, align='R')
        else:
            pdf.cell(col_widths[0], row_h, txt=str(it.get('index', '')), border=1, align='C')
            pdf.cell(col_widths[1], row_h, txt=name, border=1, align='L')
            pdf.cell(col_widths[2], row_h, txt=fmt(it['unit_price']), border=1, align='R')
            pdf.cell(col_widths[3], row_h, txt=str(it['quantity']), border=1, align='C')
            pdf.cell(col_widths[4], row_h, txt=fmt(it['unit_total']), border=1, align='R')
            pdf.cell(col_widths[5], row_h, txt=fmt(it['total']), border=1, align='R')
        pdf.ln(row_h)

    pdf.ln(6)

    # ---------- Totals ----------
    original = float(getattr(order, 'original_amount', None) or getattr(order, 'total_amount', 0))
    discount_amt = float(getattr(order, 'discount_amount', 0) or 0)
    tax_amt = float(getattr(order, 'tax_amount', 0) or getattr(order, 'tax', 0) or 0)
    grand_total = float(getattr(order, 'total_amount', 0) or 0)

    # place totals area on the right side with fixed width
    right_x = pdf.w - pdf.r_margin - 80

    pdf.set_x(right_x)
    pdf.set_font(FONT_FAMILY, '', 10)
    pdf.cell(40, 7, txt='Subtotal:', align='R')
    pdf.cell(35, 7, txt=fmt(original), ln=1, align='R')

    if discount_amt > 0:
        pdf.set_x(right_x)
        pdf.cell(40, 7, txt='Discount:', align='R')
        pdf.set_text_color(200, 0, 0)
        pdf.cell(35, 7, txt=f"-{fmt(discount_amt)}", ln=1, align='R')
        pdf.set_text_color(*dark_color)

    if tax_amt and tax_amt > 0:
        pdf.set_x(right_x)
        pdf.cell(40, 7, txt='Tax:', align='R')
        pdf.cell(35, 7, txt=fmt(tax_amt), ln=1, align='R')

    pdf.set_x(right_x)
    pdf.set_font(FONT_FAMILY, 'B', 13)
    pdf.set_text_color(*brand_color)
    pdf.cell(40, 9, txt='Grand Total:', align='R')
    pdf.cell(35, 9, txt=fmt(grand_total), ln=1, align='R')
    pdf.set_text_color(*dark_color)

    pdf.ln(4)

    # ---------- Payment & Notes ----------
    pdf.set_font(FONT_FAMILY, '', 10)
    pdf.cell(0, 6, txt=f"Payment Method: {getattr(order, 'payment_method', 'N/A')}", ln=1)
    pdf.cell(0, 6, txt=f"Payment Status: {getattr(order, 'payment_status', 'N/A')}", ln=1)
    pdf.cell(0, 6, txt=f"Order Type: {getattr(order, 'order_type', 'N/A')}", ln=1)
    if getattr(order, 'pickup_type', None):
        pdf.cell(0, 6, txt=f"Pickup: {order.pickup_type}", ln=1)

    if getattr(order, 'notes', None):
        pdf.ln(2)
        pdf.set_font(FONT_FAMILY, 'B', 10)
        pdf.cell(0, 6, txt='Notes:', ln=1)
        pdf.set_font(FONT_FAMILY, '', 10)
        pdf.multi_cell(0, 5, txt=order.notes)

    # ---------- Footer ----------
    pdf.ln(6)
    pdf.set_draw_color(*brand_color)
    y = pdf.get_y()
    pdf.line(15, y, 195, y)
    pdf.ln(4)
    pdf.set_font(FONT_FAMILY, 'B', 12)
    pdf.set_text_color(*brand_color)
    pdf.cell(0, 7, txt='Thank You For Your Order!', ln=1, align='C')
    pdf.set_font(FONT_FAMILY, 'I', 10)
    pdf.set_text_color(*dark_color)
    pdf.cell(0, 6, txt='Visit Again!', ln=1, align='C')

    # Printed timestamp (when this PDF was generated/printed)
    try:
        printed_at = format_datetime_local(timezone.now())
        pdf.set_font(FONT_FAMILY, '', 8)
        pdf.cell(0, 6, txt=f"Printed: {printed_at}", ln=1, align='R')
    except Exception:
        pass

    # Optional QR on the bottom-left
    try:
        if QR_SUPPORT:
            qr_b64 = generate_qr_code(order)
            if qr_b64:
                qr_bytes = base64.b64decode(qr_b64)
                qr_buf = BytesIO(qr_bytes)
                # place QR near bottom-left respecting bottom margin
                qr_y = pdf.h - pdf.b_margin - 30
                pdf.image(qr_buf, x=pdf.l_margin, y=qr_y, w=25, h=25)
    except Exception:
        pass

    # ---------- Output ----------
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        pdf_bytes = pdf_output.encode('latin-1')
    else:
        pdf_bytes = pdf_output

    if not pdf_bytes.startswith(b'%PDF'):
        raise RuntimeError("Generated data is not a valid PDF.")

    return pdf_bytes


def generate_receipt_text(order, bill_type='standard'):
    """Plain text fallback (used only if PDF generation fails)"""
    # ... (keep your existing implementation) ...
    line = '=' * 50
    dashed = '-' * 50
    items = order.items.all()
    lines = []
    lines.append(line)
    lines.append('          ROTI WALA')
    if order.shop:
        lines.append(f'    {order.shop.name}')
    lines.append(line)
    lines.append(f'Order No : {order.order_number}')
    lines.append(f'Date     : {format_datetime_local(order.ordered_at)}')
    lines.append('')
    lines.append(f'Customer : {order.customer_name or "Walk-in Customer"}')
    lines.append(f'Phone    : {order.customer_phone or "N/A"}')
    lines.append('')
    lines.append(dashed)
    lines.append('')
    for item in items:
        qty = item.quantity
        line_total = float(item.total_price or item.final_price or item.original_price or 0)
        price_per = line_total / qty if qty > 0 else 0
        name = item.item_name[:25].ljust(25)
        total = f"₹{line_total:.2f}".rjust(10)
        lines.append(f'{qty} x {name} {f"₹{price_per:.2f}".rjust(10)} {total}')
    lines.append('')
    lines.append(dashed)
    lines.append('')
    original = float(order.original_amount or order.total_amount)
    lines.append(f'Subtotal              ₹{original:.2f}')
    if order.discount_amount and float(order.discount_amount) > 0:
        lines.append(f'Discount              ₹-{float(order.discount_amount):.2f}')
        if order.discount_name:
            lines.append(f'  ({order.discount_name})')
    lines.append('')
    lines.append(f'Grand Total           ₹{float(order.total_amount):.2f}')
    lines.append('')
    lines.append(f'Payment    : {order.payment_method.upper()}')
    lines.append(f'Status     : {order.payment_status.upper()}')
    lines.append(f'Order Type : {order.order_type.upper()}')
    if order.pickup_type:
        lines.append(f'Pickup     : {order.pickup_type.upper()}')
    if order.notes:
        lines.append('')
        lines.append('Notes:')
        lines.append(order.notes)
    lines.append('')
    lines.append(line)
    lines.append('   Thank You For Visiting!')
    lines.append('      Visit Again!')
    lines.append(line)
    return '\n'.join(lines)


def generate_receipt_data(order, bill_type='standard'):
    """Structured receipt data for frontend (unchanged)"""
    items_data = []
    for item in order.items.all():
        line_total = float(item.original_price or item.final_price or item.total_price or 0)
        price_per = line_total / item.quantity if item.quantity > 0 else 0
        items_data.append({
            'name': item.item_name,
            'quantity': item.quantity,
            'price': price_per,
            'total': float(item.total_price),
            'discount_amount': float(item.discount_amount or 0),
            'final_price': float(item.final_price or item.total_price),
            'original_price': float(item.original_price or item.total_price),
        })
    return {
        'order_number': order.order_number,
        'order_id': str(order.id),
        'ordered_at': format_datetime_local(order.ordered_at),
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
        'pickup_type': order.pickup_type or 'N/A',
        'notes': order.notes,
        'receipt_text': generate_receipt_text(order, bill_type),
        'discount_name': order.discount_name,
        'status': order.status,
    }


def generate_qr_code(order):
    if not QR_SUPPORT:
        return None
    qr_data = f"ORDER:{order.order_number}|AMOUNT:{order.total_amount}|DATE:{order.ordered_at}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()