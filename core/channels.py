import logging
import requests
from django.conf import settings

log = logging.getLogger(__name__)


def send_sms(phone, text):
    """Africa's Talking SMS. Without an API key (dev) the message is only logged."""
    if not settings.AT_API_KEY:
        log.info("SMS (not sent, no API key) to %s: %s", phone, text)
        return
    data = {"username": settings.AT_USERNAME, "to": f"+{phone}", "message": text}
    if settings.AT_SENDER_ID:
        data["from"] = settings.AT_SENDER_ID
    r = requests.post("https://api.africastalking.com/version1/messaging", data=data,
                      headers={"apiKey": settings.AT_API_KEY, "Accept": "application/json"}, timeout=15)
    r.raise_for_status()


def send_whatsapp(phone, text):
    """WhatsApp Cloud API template message (business-initiated messages must use approved templates)."""
    if not (settings.WA_TOKEN and settings.WA_PHONE_ID and settings.WA_TEMPLATE):
        log.info("WhatsApp (not sent, not configured) to %s: %s", phone, text)
        return
    body = {"messaging_product": "whatsapp", "to": phone, "type": "template",
            "template": {"name": settings.WA_TEMPLATE, "language": {"code": "en"},
                         "components": [{"type": "body", "parameters": [{"type": "text", "text": text[:500]}]}]}}
    r = requests.post(f"https://graph.facebook.com/v20.0/{settings.WA_PHONE_ID}/messages", json=body,
                      headers={"Authorization": f"Bearer {settings.WA_TOKEN}"}, timeout=15)
    r.raise_for_status()
