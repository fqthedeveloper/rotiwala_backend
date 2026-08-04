import requests
import json
import logging
from django.conf import settings
from .models import WhatsAppMessageLog

logger = logging.getLogger(__name__)

class WhatsAppService:
    BASE_URL = settings.WHATSAPP_BASE_URL
    PHONE_NUMBER_ID = settings.WHATSAPP_PHONE_NUMBER_ID
    ACCESS_TOKEN = settings.WHATSAPP_ACCESS_TOKEN

    @classmethod
    def _send_template(cls, to_phone: str, template_name: str, components: list = None, language: str = "en"):
        if not to_phone.startswith("+"):
            to_phone = "+" + to_phone

        url = f"{cls.BASE_URL}/{cls.PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {cls.ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Rotiwaale-Django/1.0"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language}
            }
        }
        if components:
            payload["template"]["components"] = components

        # Debug (remove in production)
        print("=" * 60)
        print("WHATSAPP REQUEST:")
        print(f"URL: {url}")
        print(f"PAYLOAD: {json.dumps(payload, indent=2)}")
        print("=" * 60)

        try:
            # ⚠️ Remove verify=False in production
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
                verify=False
            )
            resp.raise_for_status()
            result = resp.json()
            WhatsAppMessageLog.objects.create(
                template_name=template_name,
                recipient=to_phone,
                parameters=components,
                status='sent',
                message_id=result.get('messages', [{}])[0].get('id', '')
            )
            print("✅ WhatsApp message sent successfully!")
            return {"success": True, "data": result}
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                error_msg = f"HTTP {e.response.status_code} – {e.response.text}"
            print(f"❌ WhatsApp API Error: {error_msg}")
            logger.error(f"WhatsApp send failed: {error_msg}")
            WhatsAppMessageLog.objects.create(
                template_name=template_name,
                recipient=to_phone,
                parameters=components,
                status='failed',
                error_message=error_msg
            )
            raise Exception(f"WhatsApp API Error: {error_msg}")

    # ---------- Public template methods ----------

    @classmethod
    def send_otp(cls, phone: str, otp_code: str):
        """Template: otp_verification – assumes 1 body parameter + button parameter"""
        components = [
            {
                "type": "body",
                "parameters": [{"type": "text", "text": otp_code}]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [{"type": "text", "text": otp_code}]
            }
        ]
        return cls._send_template(phone, "otp_verification", components)

    @classmethod
    def send_welcome(cls, phone: str, customer_name: str):
        """Template: welcome_customer – assumes 1 body parameter"""
        components = [{
            "type": "body",
            "parameters": [{"type": "text", "text": customer_name}]
        }]
        return cls._send_template(phone, "welcome_customer", components)

    @classmethod
    def send_manager_new_order(cls, manager_phone: str, order_id: str, customer_name: str, total: str, pickup_time: str):
        """
        Template: manager_new_order
        Placeholders: {{1}} Order Number, {{2}} Customer Name, {{3}} Total Amount, {{4}} Pickup Time
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": order_id},
                {"type": "text", "text": customer_name},
                {"type": "text", "text": total},
                {"type": "text", "text": pickup_time}
            ]
        }]
        return cls._send_template(manager_phone, "manager_new_order", components)

    @classmethod
    def send_order_accepted(cls, customer_phone: str, customer_name: str, order_id: str, prep_time_minutes: str):
        """
        Template: order_accepted_v1
        Placeholders: {{1}} Customer Name, {{2}} Order Number, {{3}} Estimated Prep Time (minutes)
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": customer_name},
                {"type": "text", "text": order_id},
                {"type": "text", "text": prep_time_minutes}
            ]
        }]
        return cls._send_template(customer_phone, "order_accepted_v1", components)

    @classmethod
    def send_order_rejected(cls, customer_phone: str, order_id: str, reason: str):
        """
        Template: order_rejected
        Placeholders: {{1}} Order Number, {{2}} Reason
        """
        # Provide a default reason if none given
        if not reason:
            reason = "not specified"
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": order_id},
                {"type": "text", "text": reason}
            ]
        }]
        return cls._send_template(customer_phone, "order_rejected", components)

    @classmethod
    def send_order_ready(cls, customer_phone: str, order_id: str, shop_name: str):
        """
        Template: order_ready
        Placeholders: {{1}} Order Number, {{2}} Shop Name
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": order_id},
                {"type": "text", "text": shop_name}
            ]
        }]
        return cls._send_template(customer_phone, "order_ready", components)

    @classmethod
    def send_pickup_reminder(cls, phone: str, order_id: str, time: str):
        """
        Template: pickup_reminder
        Placeholders: {{1}} Order Number, {{2}} Pickup Time
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": order_id},
                {"type": "text", "text": time}
            ]
        }]
        return cls._send_template(phone, "pickup_reminder", components)

    @classmethod
    def send_discount_offer(cls, phone: str, code: str, discount: str):
        """
        Template: discount_offer – adjust placeholders if needed
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": code},
                {"type": "text", "text": discount}
            ]
        }]
        return cls._send_template(phone, "discount_offer", components)

    @classmethod
    def send_coupon_offer(cls, phone: str, coupon: str):
        """
        Template: coupon_offer – adjust placeholders if needed
        """
        components = [{
            "type": "body",
            "parameters": [{"type": "text", "text": coupon}]
        }]
        return cls._send_template(phone, "coupon_offer", components)

    @classmethod
    def send_manager_order_cancelled(cls, manager_phone: str, order_id: str, customer_name: str):
        """
        Template: manager_order_cancelled (or manager_order_canc)
        Placeholders: {{1}} Order Number, {{2}} Customer Name
        """
        components = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": order_id},
                {"type": "text", "text": customer_name}
            ]
        }]
        return cls._send_template(manager_phone, "manager_order_cancelled", components)