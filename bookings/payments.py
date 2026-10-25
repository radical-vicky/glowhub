from decimal import Decimal
from django.db import transaction
from core.services import audit, notify
from django.utils import timezone
from .models import Booking, PaymentAttempt, PaymentEvent


@transaction.atomic
def handle_callback(payload):
    """Idempotent, amount-verified processing of an STK callback."""
    cb = payload.get("Body", {}).get("stkCallback", {})
    attempt = (PaymentAttempt.objects.select_for_update()
               .filter(checkout_request_id=cb.get("CheckoutRequestID")).first())
    PaymentEvent.objects.create(attempt=attempt, payload=payload)  # append-only
    if not attempt or attempt.status in (PaymentAttempt.Status.SUCCESS, PaymentAttempt.Status.REFUNDED):
        return  # unknown or duplicate callback: no further effect

    attempt.result_desc = str(cb.get("ResultDesc", ""))[:255]
    if cb.get("ResultCode") != 0:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.save()
        return

    items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
    paid = Decimal(str(items.get("Amount", 0)))
    booking = Booking.objects.select_for_update().get(pk=attempt.booking_id)
    attempt.mpesa_receipt = items.get("MpesaReceiptNumber")

    amount_ok = paid >= attempt.amount
    still_valid = booking.status == Booking.Status.PENDING_PAYMENT
    if amount_ok and still_valid:  # note: late payment on a still-pending booking is accepted
        attempt.status = PaymentAttempt.Status.SUCCESS
        booking.transition(Booking.Status.CONFIRMED, note=f"M-Pesa {attempt.mpesa_receipt}")
        transaction.on_commit(lambda: _confirmed_emails(booking, attempt))
    else:
        # Money received but booking cannot be confirmed (expired/cancelled/wrong amount):
        # never silently drop it, staff must reconcile or refund.
        attempt.status = PaymentAttempt.Status.RECONCILIATION_REQUIRED
        audit(None, "payment.needs_reconciliation", attempt.pk, receipt=attempt.mpesa_receipt)
    attempt.save()


def expire_stale_bookings():
    """Run from cron/Celery beat: `python manage.py expire_bookings`."""
    qs = Booking.objects.filter(status=Booking.Status.PENDING_PAYMENT, expires_at__lt=timezone.now())
    for b in qs:
        b.transition(Booking.Status.EXPIRED, note="Payment window elapsed")


def _confirmed_emails(booking, attempt):
    when = booking.start.strftime("%a %d %b, %H:%M")
    notify(booking.customer, "Booking confirmed",
           f"{booking.service_name} at {booking.business.name}, {when}.\n"
           f"Deposit received: KSh {booking.deposit_amount:.0f} (receipt {attempt.mpesa_receipt}).\n"
           f"Balance due: KSh {booking.balance:.0f}.", urgent=True)
    notify(booking.business.owner, "New confirmed booking", f"{booking.service_name}, {when}, {booking.contact_name}.")


def request_refund(booking, reason, requested_by):
    """Create a refund request for the successful deposit. Staff approve it in the admin."""
    from .models import Refund
    pay = booking.payments.filter(status=PaymentAttempt.Status.SUCCESS).first()
    if not pay:
        return None
    pay.status = PaymentAttempt.Status.REFUND_PENDING
    pay.save(update_fields=["status"])
    audit(requested_by, "refund.requested", pay.pk, booking=booking.pk, reason=reason)
    return Refund.objects.create(payment=pay, amount=pay.amount, reason=reason[:200], requested_by=requested_by)


def reconcile_pending(min_age_minutes=3):
    """Resolve uncertain STK outcomes by querying Safaricom. Safe to run repeatedly."""
    from datetime import timedelta
    from . import mpesa
    cutoff = timezone.now() - timedelta(minutes=min_age_minutes)
    for a in PaymentAttempt.objects.filter(status=PaymentAttempt.Status.PENDING, created_at__lt=cutoff):
        try:
            res = mpesa.stk_query(a.checkout_request_id)
        except Exception:
            continue
        code = str(res.get("ResultCode", ""))
        if code == "":
            continue
        with transaction.atomic():
            a = PaymentAttempt.objects.select_for_update().get(pk=a.pk)
            if a.status != PaymentAttempt.Status.PENDING:
                continue
            PaymentEvent.objects.create(attempt=a, payload=res)
            a.result_desc = str(res.get("ResultDesc", ""))[:255]
            if code != "0":
                a.status = PaymentAttempt.Status.FAILED
            else:
                b = Booking.objects.select_for_update().get(pk=a.booking_id)
                if b.status == Booking.Status.PENDING_PAYMENT:
                    a.status = PaymentAttempt.Status.SUCCESS
                    b.transition(Booking.Status.CONFIRMED, note="Confirmed by reconciliation query")
                else:
                    a.status = PaymentAttempt.Status.RECONCILIATION_REQUIRED
                    audit(None, "payment.needs_reconciliation", a.pk)
            a.save()
    n = PaymentAttempt.objects.filter(status=PaymentAttempt.Status.RECONCILIATION_REQUIRED).count()
    if n:
        from django.core.mail import mail_admins
        mail_admins("Payments need reconciliation", f"{n} payment(s) require manual review in the admin.", fail_silently=True)
