from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.availability import slots_for
from bookings.models import Booking, PaymentAttempt
from bookings.payments import handle_callback
from bookings.views import deposit_for
from marketplace.models import Business, BusinessHours, Service
from subscriptions.services import start_trial

U = get_user_model()


def cb(checkout, amount=750, code=0):
    body = {"CheckoutRequestID": checkout, "ResultCode": code, "ResultDesc": "ok"}
    if code == 0:
        body["CallbackMetadata"] = {"Item": [{"Name": "Amount", "Value": amount}, {"Name": "MpesaReceiptNumber", "Value": "ABC123"}]}
    return {"Body": {"stkCallback": body}}


class Base(TestCase):
    def setUp(self):
        self.owner = U.objects.create_user("owner", "o@x.com", "pw")
        self.cust = U.objects.create_user("cust", "c@x.com", "pw")
        self.other = U.objects.create_user("other", "x@x.com", "pw")
        self.biz = Business.objects.create(owner=self.owner, name="Luxe", slug="luxe", area="Nairobi", status="APPROVED")
        for d in range(7):
            BusinessHours.objects.create(business=self.biz, weekday=d, opens=time(9), closes=time(18))
        self.svc = Service.objects.create(business=self.biz, name="Braids", price=1500, duration_minutes=90)
        self.day = (timezone.now() + timedelta(days=3)).date()

    def make_booking(self, status="PENDING_PAYMENT", expires_in=10):
        start = slots_for(self.svc, self.day)[0]
        return Booking.objects.create(
            customer=self.cust, business=self.biz, service=self.svc, start=start,
            end=start + timedelta(minutes=90), status=status,
            expires_at=timezone.now() + timedelta(minutes=expires_in), service_name="Braids",
            price=1500, deposit_amount=750, duration_minutes=90, policy_snapshot="p",
            contact_name="C", contact_phone="254712345678")

    def make_attempt(self, b):
        return PaymentAttempt.objects.create(booking=b, phone=b.contact_phone, amount=750,
                                             status="PENDING", checkout_request_id="CK1")


class MoneyAndSlots(Base):
    def test_deposit_rounding(self):
        self.assertEqual(deposit_for(Decimal("2000"), 50), Decimal("1000"))
        self.assertEqual(deposit_for(Decimal("1501"), 50), Decimal("751"))

    def test_taken_slot_not_offered(self):
        b = self.make_booking()
        self.assertNotIn(b.start, slots_for(self.svc, self.day))

    def test_expired_pending_releases_slot(self):
        b = self.make_booking(expires_in=-1)
        self.assertIn(b.start, slots_for(self.svc, self.day))


class Callbacks(Base):
    def test_success_confirms_and_duplicate_is_noop(self):
        b = self.make_booking()
        a = self.make_attempt(b)
        handle_callback(cb("CK1"))
        handle_callback(cb("CK1"))
        b.refresh_from_db(); a.refresh_from_db()
        self.assertEqual(b.status, "CONFIRMED")
        self.assertEqual(a.status, "SUCCESS")
        self.assertEqual(b.events.count(), 1)

    def test_late_payment_on_expired_booking_needs_reconciliation(self):
        b = self.make_booking(status="EXPIRED")
        a = self.make_attempt(b)
        handle_callback(cb("CK1"))
        b.refresh_from_db(); a.refresh_from_db()
        self.assertEqual(b.status, "EXPIRED")
        self.assertEqual(a.status, "RECONCILIATION_REQUIRED")

    def test_underpayment_does_not_confirm(self):
        b = self.make_booking()
        a = self.make_attempt(b)
        handle_callback(cb("CK1", amount=100))
        b.refresh_from_db()
        self.assertEqual(b.status, "PENDING_PAYMENT")

    def test_illegal_transition(self):
        b = self.make_booking(status="EXPIRED")
        with self.assertRaises(ValueError):
            b.transition("CONFIRMED")

    def test_bad_callback_secret_rejected(self):
        r = self.client.post(reverse("mpesa_callback", args=["wrong"]), "{}", content_type="application/json")
        self.assertEqual(r.status_code, 404)


class Authorization(Base):
    def test_other_customer_cannot_open_payment_page(self):
        b = self.make_booking()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("pay", args=[b.pk])).status_code, 404)

    def test_stranger_cannot_read_messages(self):
        b = self.make_booking(status="CONFIRMED")
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse("thread", args=[b.pk])).status_code, 404)

    def test_provider_cannot_act_on_other_business_booking(self):
        b = self.make_booking(status="CONFIRMED")
        self.client.force_login(self.other)
        r = self.client.post(reverse("provider_action", args=[b.pk, "cancel"]))
        self.assertEqual(r.status_code, 404)

    def test_expired_subscription_blocks_inventory(self):
        sub = start_trial(self.biz)
        sub.period_end = timezone.now() - timedelta(days=30)
        sub.save()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("inventory")).status_code, 404)

    def test_trial_unlocks_inventory(self):
        start_trial(self.biz)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse("inventory")).status_code, 200)
