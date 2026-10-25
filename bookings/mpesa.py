import base64
import re
from datetime import datetime

import requests
from django.conf import settings

TIMEOUT = 20


def _base():
    return "https://api.safaricom.co.ke" if settings.MPESA["ENV"] == "production" else "https://sandbox.safaricom.co.ke"


def normalize_phone(raw):
    p = re.sub(r"[\s\-+]", "", raw or "")
    if re.fullmatch(r"0[17]\d{8}", p):
        p = "254" + p[1:]
    if not re.fullmatch(r"254[17]\d{8}", p):
        raise ValueError("Enter a valid Safaricom number, e.g. 0712 345 678.")
    return p


def _token():
    r = requests.get(f"{_base()}/oauth/v1/generate?grant_type=client_credentials",
                     auth=(settings.MPESA["KEY"], settings.MPESA["SECRET"]), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()["access_token"]


def stk_push(phone, amount, reference, description, callback_path="book/mpesa/callback"):
    """Send an STK push. The customer enters their PIN on their own phone; we never see it."""
    c = settings.MPESA
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    pwd = base64.b64encode(f"{c['SHORTCODE']}{c['PASSKEY']}{ts}".encode()).decode()
    body = {
        "BusinessShortCode": c["SHORTCODE"], "Password": pwd, "Timestamp": ts,
        "TransactionType": "CustomerPayBillOnline", "Amount": int(amount),
        "PartyA": phone, "PartyB": c["SHORTCODE"], "PhoneNumber": phone,
        "CallBackURL": f"{c['CALLBACK_BASE']}/{callback_path}/{c['CALLBACK_SECRET']}/",
        "AccountReference": reference[:12], "TransactionDesc": description[:13],
    }
    r = requests.post(f"{_base()}/mpesa/stkpush/v1/processrequest", json=body,
                      headers={"Authorization": f"Bearer {_token()}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def stk_query(checkout_request_id):
    """Ask Safaricom for the outcome of an STK request (used for reconciliation)."""
    c = settings.MPESA
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    pwd = base64.b64encode(f"{c['SHORTCODE']}{c['PASSKEY']}{ts}".encode()).decode()
    r = requests.post(f"{_base()}/mpesa/stkpushquery/v1/query",
                      json={"BusinessShortCode": c["SHORTCODE"], "Password": pwd, "Timestamp": ts,
                            "CheckoutRequestID": checkout_request_id},
                      headers={"Authorization": f"Bearer {_token()}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def b2c(phone, amount, remarks, occasion, originator_id):
    """Business-to-customer payment (payouts, reward withdrawals). Requires Safaricom B2C approval."""
    c = settings.MPESA
    body = {"OriginatorConversationID": originator_id, "InitiatorName": c["INITIATOR"],
            "SecurityCredential": c["SECURITY_CREDENTIAL"], "CommandID": "BusinessPayment",
            "Amount": int(amount), "PartyA": c["B2C_SHORTCODE"], "PartyB": phone,
            "Remarks": remarks[:100], "Occasion": occasion[:100],
            "QueueTimeOutURL": f"{c['CALLBACK_BASE']}/earnings/mpesa/timeout/{c['CALLBACK_SECRET']}/",
            "ResultURL": f"{c['CALLBACK_BASE']}/earnings/mpesa/result/{c['CALLBACK_SECRET']}/"}
    r = requests.post(f"{_base()}/mpesa/b2c/v3/paymentrequest", json=body,
                      headers={"Authorization": f"Bearer {_token()}"}, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
