from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from accounts.services import get_profile
from bookings.tests.test_core import Base
from payouts.models import LedgerEntry
from payouts.services import balances, credit_booking, request_payout


class Ledger(Base):
    def test_confirmation_credits_deposit_minus_fee_once(self):
        b = self.make_booking()
        b.transition("CONFIRMED")
        credit_booking(b)  # repeat: must not duplicate
        self.assertEqual(LedgerEntry.objects.filter(business=self.biz).count(), 2)
        self.assertEqual(LedgerEntry.objects.get(kind="FEE").amount, Decimal("-75.00"))

    def test_cancellation_nets_to_zero(self):
        b = self.make_booking()
        b.transition("CONFIRMED")
        b.transition("CANCELLED_BY_PROVIDER")
        total = sum(e.amount for e in LedgerEntry.objects.filter(business=self.biz))
        self.assertEqual(total, 0)

    def _ready(self):
        self.biz.verified = True
        self.biz.save()
        p = get_profile(self.owner)
        p.phone, p.phone_verified = "254733333333", True
        p.save()
        LedgerEntry.objects.create(business=self.biz, kind="DEPOSIT", amount=1000, available_at=timezone.now() - timedelta(hours=1))

    def test_payout_reserves_balance(self):
        self._ready()
        request_payout(self.biz, 500, self.owner)
        self.assertEqual(balances(self.biz)["available"], 500)

    def test_cannot_overdraw_or_double_request(self):
        self._ready()
        with self.assertRaises(ValueError):
            request_payout(self.biz, 5000, self.owner)
        request_payout(self.biz, 500, self.owner)
        with self.assertRaises(ValueError):
            request_payout(self.biz, 500, self.owner)

    def test_unverified_business_cannot_request(self):
        self._ready()
        self.biz.verified = False
        self.biz.save()
        with self.assertRaises(ValueError):
            request_payout(self.biz, 500, self.owner)
