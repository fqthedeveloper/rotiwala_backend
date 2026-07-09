from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from .models import Discount, DiscountUsage
from .coupon_models import Coupon, CouponUsage
from .services import get_discounted_price
from .offer_validation import customer_used_discount, customer_used_coupon


class OfferResult:
    def __init__(self):
        self.success = True
        self.message = ""
        self.original_price = Decimal("0.00")
        self.discount_amount = Decimal("0.00")
        self.final_price = Decimal("0.00")
        self.promotion_type = "none"
        self.promotion = None
        self.discount = None
        self.coupon = None
        self.discount_name = None
        self.coupon_code = None
        self.discount_type = None
        self.discount_value = Decimal("0.00")
        self.has_offer = False

    def to_dict(self):
        return {
            "success": self.success,
            "message": self.message,
            "has_offer": self.has_offer,
            "promotion_type": self.promotion_type,
            "original_price": self.original_price,
            "discount_amount": self.discount_amount,
            "final_price": self.final_price,
            "discount_name": self.discount_name,
            "coupon_code": self.coupon_code,
            "discount_type": self.discount_type,
            "discount_value": self.discount_value,
        }


class OfferEngine:
    def __init__(self, customer, shop, coupon_code=None, forced_discount=None):
        self.customer = customer
        self.shop = shop
        self.coupon_code = coupon_code
        self.forced_discount = forced_discount

    # -------------------------
    # Empty Result
    # -------------------------
    def empty_result(self, price):
        result = OfferResult()
        result.original_price = Decimal(price)
        result.final_price = Decimal(price)
        return result

    # -------------------------
    # Customer already used Discount
    # -------------------------
    def discount_used(self, discount):
        return customer_used_discount(self.customer, discount)

    # -------------------------
    # Customer already used Coupon
    # -------------------------
    def coupon_used(self, coupon):
        return customer_used_coupon(self.customer, coupon)

    # -------------------------
    # Percentage & Fixed helpers
    # -------------------------
    def percentage_discount(self, amount, percentage):
        amount = Decimal(amount)
        percentage = Decimal(percentage)
        return (amount * percentage / Decimal("100")).quantize(Decimal("0.01"))

    def fixed_discount(self, amount, value):
        amount = Decimal(amount)
        value = Decimal(value)
        if value > amount:
            value = amount
        return value.quantize(Decimal("0.01"))

    def final_price(self, original, discount):
        total = Decimal(original) - Decimal(discount)
        if total < 0:
            total = Decimal("0.00")
        return total.quantize(Decimal("0.01"))

    # ==========================================
    # APPLY DISCOUNT (supports cart/category totals)
    # ==========================================
    def apply_discount(self, menu_item, quantity, discount, cart_total=None, category_total=None):
        quantity = int(quantity)
        item_subtotal = Decimal(menu_item.base_price) * quantity
        result = OfferResult()
        result.original_price = item_subtotal
        result.final_price = item_subtotal
        result.discount_amount = Decimal("0.00")

        # --- validation ---
        now = timezone.now()
        if not discount.is_active or discount.start_date > now or discount.end_date < now:
            result.message = "Discount is not active or expired."
            return result
        if self.discount_used(discount):
            result.message = "Discount already used."
            return result

        # --- Determine the total against which the discount is applied ---
        if discount.apply_on == 'shop':
            order_total = Decimal(cart_total) if cart_total is not None else item_subtotal
        elif discount.apply_on == 'category':
            # Only items in this category should be considered
            if menu_item.category_id and discount.category_id and menu_item.category_id == discount.category_id:
                order_total = Decimal(category_total) if category_total is not None else item_subtotal
            else:
                result.message = "Not applicable to this category."
                return result
        else:  # item
            order_total = item_subtotal

        # --- Minimum order check ---
        if order_total < discount.minimum_order_amount:
            result.message = f"Minimum order ₹{discount.minimum_order_amount}"
            return result

        # --- Applicability for item ---
        if discount.apply_on == 'item' and menu_item != discount.menu_item:
            result.message = "Not applicable to this item."
            return result

        # --- Compute total discount on order_total ---
        if discount.discount_type == "percentage":
            total_discount = self.percentage_discount(order_total, discount.value)
        else:  # fixed
            total_discount = self.fixed_discount(order_total, discount.value)

        # Cap if maximum_discount_amount is set
        if discount.maximum_discount_amount and total_discount > discount.maximum_discount_amount:
            total_discount = discount.maximum_discount_amount

        # --- Allocate proportionally ---
        if order_total > 0:
            item_discount = total_discount * (item_subtotal / order_total)
        else:
            item_discount = Decimal("0.00")
        item_discount = item_discount.quantize(Decimal("0.01"))

        final_price = item_subtotal - item_discount
        result.discount_amount = item_discount
        result.final_price = final_price
        result.has_offer = True
        result.promotion_type = "discount"
        result.discount = discount
        result.promotion = discount
        result.discount_name = discount.name
        result.discount_type = discount.discount_type
        result.discount_value = discount.value
        result.message = "Discount applied."
        return result

    # ==========================================
    # GET AUTOMATIC DISCOUNT (with totals)
    # ==========================================
    def get_discount_offer(self, menu_item, quantity=1, cart_total=None, category_total=None):
        service = get_discounted_price(menu_item)
        discount = service["discount"]
        if discount is None:
            result = self.empty_result(service["original_price"] * quantity)
            return result
        return self.apply_discount(menu_item, quantity, discount, cart_total, category_total)

    # ==========================================
    # COUPON LOGIC
    # ==========================================
    def get_coupon(self):
        if not self.coupon_code:
            return None
        try:
            return Coupon.objects.get(
                code__iexact=self.coupon_code.strip(),
                shop=self.shop,
                status="active"
            )
        except Coupon.DoesNotExist:
            return None

    def validate_coupon(self, coupon, total_amount):
        now = timezone.now()
        if coupon is None:
            return False, "Invalid coupon."
        if now < coupon.start_date:
            return False, "Coupon not started."
        if now > coupon.end_date:
            return False, "Coupon expired."
        if self.coupon_used(coupon):
            return False, "Coupon already used."
        if Decimal(total_amount) < coupon.minimum_order_amount:
            return False, f"Minimum order ₹{coupon.minimum_order_amount}"
        if coupon.first_order_only:
            total_orders = self.customer.orders.count()
            if total_orders > 0:
                return False, "Coupon valid only for first order."
        return True, "Coupon valid."

    def calculate_coupon(self, amount, coupon):
        amount = Decimal(amount)
        if coupon.discount_type == "percentage":
            discount = amount * Decimal(coupon.value) / Decimal("100")
        else:
            discount = Decimal(coupon.value)
        if coupon.maximum_discount_amount and discount > coupon.maximum_discount_amount:
            discount = coupon.maximum_discount_amount
        if discount > amount:
            discount = amount
        final_price = amount - discount
        return discount.quantize(Decimal("0.01")), final_price.quantize(Decimal("0.01"))

    def get_coupon_offer(self, total_amount):
        result = OfferResult()
        result.original_price = Decimal(total_amount)
        result.final_price = Decimal(total_amount)

        coupon = self.get_coupon()
        valid, message = self.validate_coupon(coupon, total_amount)
        if not valid:
            result.message = message
            return result

        discount_amount, final_price = self.calculate_coupon(total_amount, coupon)
        result.has_offer = True
        result.promotion_type = "coupon"
        result.promotion = coupon
        result.coupon = coupon
        result.coupon_code = coupon.code
        result.discount_name = coupon.name
        result.discount_type = coupon.discount_type
        result.discount_value = coupon.value
        result.discount_amount = discount_amount
        result.final_price = final_price
        result.message = "Coupon applied."
        return result

    # ==========================================
    # BEST OFFER
    # ==========================================
    def get_best_offer(self, menu_item, quantity=1, cart_total=None, category_total=None):
        if self.forced_discount is not None:
            return self.apply_discount(menu_item, quantity, self.forced_discount, cart_total, category_total)

        discount_offer = self.get_discount_offer(menu_item, quantity, cart_total, category_total)
        coupon_offer = self.get_coupon_offer(discount_offer.original_price)
        return self.compare_offers(discount_offer, coupon_offer)

    def compare_offers(self, discount_offer, coupon_offer):
        if not discount_offer.has_offer and not coupon_offer.has_offer:
            return discount_offer
        if coupon_offer.has_offer and not discount_offer.has_offer:
            return coupon_offer
        if discount_offer.has_offer and not coupon_offer.has_offer:
            return discount_offer
        if coupon_offer.discount_amount > discount_offer.discount_amount:
            coupon_offer.message = "Coupon gives better savings."
            return coupon_offer
        if discount_offer.discount_amount > coupon_offer.discount_amount:
            discount_offer.message = "Automatic discount gives better savings."
            return discount_offer
        discount_offer.message = "Automatic discount applied."
        return discount_offer

    # ==========================================
    # CART CALCULATION (with rounding)
    # ==========================================
    def calculate_cart_item(self, cart_item, cart_total=None, category_total=None):
        return self.get_best_offer(
            menu_item=cart_item.menu_item,
            quantity=cart_item.quantity,
            cart_total=cart_total,
            category_total=category_total
        )

    def calculate_cart(self, cart_items):
        # 1. Compute total original amount and category totals
        total_original = Decimal("0.00")
        category_totals = {}
        for item in cart_items:
            item_total = Decimal(item.menu_item.base_price) * item.quantity
            total_original += item_total
            cat_id = item.menu_item.category_id
            if cat_id:
                category_totals[cat_id] = category_totals.get(cat_id, Decimal("0.00")) + item_total

        # 2. Process each item to get offers (without rounding yet)
        item_results = []
        total_discount = Decimal("0.00")
        total_final = Decimal("0.00")

        for item in cart_items:
            offer = self.get_best_offer(
                menu_item=item.menu_item,
                quantity=item.quantity,
                cart_total=total_original,
                category_total=category_totals.get(item.menu_item.category_id, Decimal("0.00"))
            )
            item_results.append({"item": item, "offer": offer})
            total_discount += offer.discount_amount
            total_final += offer.final_price

        # 3. Round the final total to nearest rupee (0.5 rounds up)
        rounded_final = total_final.quantize(Decimal('1'), rounding=ROUND_HALF_UP)

        # 4. Adjust discount so that: original - discount = rounded_final
        adjusted_discount = total_original - rounded_final
        if adjusted_discount < 0:
            adjusted_discount = Decimal("0.00")
            rounded_final = total_original

        # 5. Proportionally adjust each item's discount so that the sum equals adjusted_discount
        if total_discount > 0 and adjusted_discount != total_discount:
            scale = adjusted_discount / total_discount if total_discount else Decimal("0")
            for item_result in item_results:
                old_discount = item_result["offer"].discount_amount
                new_discount = (old_discount * scale).quantize(Decimal("0.01"))
                item_result["offer"].discount_amount = new_discount
                item_result["offer"].final_price = item_result["offer"].original_price - new_discount

        return {
            "items": item_results,
            "original_total": total_original,
            "discount_total": adjusted_discount,
            "final_total": rounded_final,
            "saved": adjusted_discount,
        }