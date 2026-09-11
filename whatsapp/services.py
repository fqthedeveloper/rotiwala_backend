import json
import logging
import requests

from django.conf import settings

from .models import WhatsAppMessageLog

logger = logging.getLogger(__name__)


class WhatsAppService:

    @classmethod
    def _send_template(
        cls,
        to_phone: str,
        template_name: str,
        components: list = None,
        language: str = "en"
    ):

        # Read settings every request (avoids stale values)
        base_url = settings.WHATSAPP_BASE_URL.rstrip("/")
        phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        access_token = settings.WHATSAPP_ACCESS_TOKEN

        if not to_phone.startswith("+"):
            to_phone = "+" + to_phone

        url = f"{base_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "User-Agent": "Rotiwaale-Django/1.0",
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language
                }
            }
        }

        if components:
            payload["template"]["components"] = components

        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
                verify=False,      # Remove in production
            )

            print("STATUS :", resp.status_code)
            print("BODY   :", resp.text)

            resp.raise_for_status()

            result = resp.json()

            WhatsAppMessageLog.objects.create(
                template_name=template_name,
                recipient=to_phone,
                parameters=components,
                status="sent",
                message_id=result.get("messages", [{}])[0].get("id", "")
            )

            logger.info("WhatsApp message sent successfully")

            return {
                "success": True,
                "data": result
            }

        except requests.exceptions.RequestException as e:

            if e.response is not None:
                error_msg = (
                    f"HTTP {e.response.status_code} – "
                    f"{e.response.text}"
                )
            else:
                error_msg = str(e)

            logger.error("WhatsApp API Error: %s", error_msg)

            WhatsAppMessageLog.objects.create(
                template_name=template_name,
                recipient=to_phone,
                parameters=components,
                status="failed",
                error_message=error_msg
            )

            raise Exception(f"WhatsApp API Error: {error_msg}")

    # ======================================================
    # OTP
    # ======================================================

    @classmethod
    def send_otp(cls, phone, otp_code):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": otp_code
                    }
                ]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [
                    {
                        "type": "text",
                        "text": otp_code
                    }
                ]
            }
        ]

        return cls._send_template(
            phone,
            "otp_verification",
            components
        )

    # ======================================================
    # Welcome
    # ======================================================

    @classmethod
    def send_welcome(cls, phone, customer_name):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": customer_name
                    }
                ]
            }
        ]

        return cls._send_template(
            phone,
            "welcome_customer",
            components
        )

    # ======================================================
    # Manager New Order
    # ======================================================

    @classmethod
    def send_manager_new_order(
        cls,
        manager_phone,
        order_id,
        customer_name,
        total,
        pickup_time
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": customer_name
                    },
                    {
                        "type": "text",
                        "text": total
                    },
                    {
                        "type": "text",
                        "text": pickup_time
                    }
                ]
            }
        ]

        return cls._send_template(
            manager_phone,
            "manager_new_order",
            components
        )

    # ======================================================
    # Order Accepted
    # ======================================================

    @classmethod
    def send_order_accepted(
        cls,
        customer_phone,
        customer_name,
        order_id,
        prep_time
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": customer_name
                    },
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": prep_time
                    }
                ]
            }
        ]

        return cls._send_template(
            customer_phone,
            "order_accepted_v1",
            components
        )

    # ======================================================
    # Order Rejected
    # ======================================================

    @classmethod
    def send_order_rejected(
        cls,
        customer_phone,
        order_id,
        reason
    ):

        if not reason:
            reason = "Not specified"

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": reason
                    }
                ]
            }
        ]

        return cls._send_template(
            customer_phone,
            "order_rejected",
            components
        )

    # ======================================================
    # Order Ready
    # ======================================================

    @classmethod
    def send_order_ready(
        cls,
        customer_phone,
        order_id,
        shop_name
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": shop_name
                    }
                ]
            }
        ]

        return cls._send_template(
            customer_phone,
            "order_ready",
            components
        )

    # ======================================================
    # Pickup Reminder
    # ======================================================

    @classmethod
    def send_pickup_reminder(
        cls,
        phone,
        order_id,
        pickup_time
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": pickup_time
                    }
                ]
            }
        ]

        return cls._send_template(
            phone,
            "pickup_reminder",
            components
        )

    # ======================================================
    # Discount Offer
    # ======================================================

    @classmethod
    def send_discount_offer(
        cls,
        phone,
        code,
        discount
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": code
                    },
                    {
                        "type": "text",
                        "text": discount
                    }
                ]
            }
        ]

        return cls._send_template(
            phone,
            "discount_offer",
            components
        )

    # ======================================================
    # Coupon Offer
    # ======================================================

    @classmethod
    def send_coupon_offer(
        cls,
        phone,
        coupon
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": coupon
                    }
                ]
            }
        ]

        return cls._send_template(
            phone,
            "coupon_offer",
            components
        )

    # ======================================================
    # Manager Order Cancelled
    # ======================================================

    @classmethod
    def send_manager_order_cancelled(
        cls,
        manager_phone,
        order_id,
        customer_name
    ):

        components = [
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": order_id
                    },
                    {
                        "type": "text",
                        "text": customer_name
                    }
                ]
            }
        ]

        return cls._send_template(
            manager_phone,
            "manager_order_cancelled",
            components
        )