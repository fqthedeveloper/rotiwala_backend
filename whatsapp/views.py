import json
import hmac
import hashlib
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import WhatsAppMessageLog

logger = logging.getLogger(__name__)

def index(request):
    return HttpResponse("WhatsApp webhook is at /whatsapp/webhook/")

@csrf_exempt
def webhook(request):
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")
        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge)
        return HttpResponse("Verification failed", status=403)

    elif request.method == "POST":
        signature = request.headers.get("X-Hub-Signature-256")
        if signature and settings.WHATSAPP_APP_SECRET:
            payload = request.body
            expected = hmac.new(
                settings.WHATSAPP_APP_SECRET.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, f"sha256={expected}"):
                logger.warning("Invalid signature")
                return HttpResponse("Invalid signature", status=403)

        try:
            data = json.loads(request.body)
            logger.info(f"WhatsApp webhook received: {data}")
            # Optionally process delivery statuses here
            return JsonResponse({"status": "ok"})
        except Exception as e:
            logger.error(f"Webhook processing error: {e}")
            return HttpResponse("Error", status=500)

    return HttpResponse("Method not allowed", status=405)