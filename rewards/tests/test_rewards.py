from datetime import timedelta
from django.test import override_settings
from django.utils import timezone

from accounts.services import get_profile
from bookings.models import PaymentAttempt
from bookings.tests.test_core import Base
from rewards.models import DiamondEntry, Referral
from rewards.services import award, balance, request_withdrawal


def verify(user, phone):
    p = get_profile(user)
    p.phone, p.phone_verified = phone, True
    p.save()


class Rewards(Base):
    def setUp(self):
        super().setUp()
        verify(self.cust, "254711111111")
        verify(self.other, "254722222222")

    def _old_credit(self, user, amount=2000):
        DiamondEntry.objects.create(user=user, amount=amount, kind="X", available_at=timezone.now() - timedelta(days=1))
        user.date_joined = timezone.now() - timedelta(days=30)
        user.save()

    def test_award_is_idempotent(self):
        award(self.cust, 100, "PROFILE", "k1")
        award(self.cust, 100, "PROFILE", "k1")
        self.assertEqual(DiamondEntry.objects.filter(user=self.cust).count(), 1)

    def test_daily_cap(self):
        self.assertIsNotNone(award(self.cust, 900, "BOOKING", "a"))
        self.assertIsNone(award(self.cust, 900, "BOOKING", "b"))

    def test_frozen_account_earns_nothing(self):
        p = get_profile(self.cust)
        p.rewards_frozen = True
        p.save()
        self.assertIsNone(award(self.cust, 100, "PROFILE", "z"))

    def test_new_diamonds_are_held(self):
        award(self.cust, 100, "PROFILE", "h")
        self.assertEqual(balance(self.cust), {"available": 0, "pending": 100})

    @override_settings(WITHDRAWALS_ENABLED=True)
    def test_withdrawal_debits_ledger(self):
        self._old_credit(self.cust)
        w = request_withdrawal(self.cust, 1000)
        self.assertEqual(w.kes, 100)
        self.assertEqual(balance(self.cust)["available"], 1000)

    @override_settings(WITHDRAWALS_ENABLED=True)
    def test_cannot_withdraw_more_than_available(self):
        self._old_credit(self.cust, 1000)
        with self.assertRaises(ValueError):
            request_withdrawal(self.cust, 2000)

    @override_settings(WITHDRAWALS_ENABLED=True)
    def test_unverified_phone_cannot_withdraw(self):
        p = get_profile(self.cust)
        p.phone_verified = False
        p.save()
        self._old_credit(self.cust)
        with self.assertRaises(ValueError):
            request_withdrawal(self.cust, 1000)

    def test_withdrawals_closed_by_default(self):
        self._old_credit(self.cust)
        with self.assertRaises(ValueError):
            request_withdrawal(self.cust, 1000)

    def test_referral_rewarded_once_after_paid_completed_booking(self):
        Referral.objects.create(referrer=self.other, referee=self.cust)
        b = self.make_booking(status="CONFIRMED")
        PaymentAttempt.objects.create(booking=b, phone="254711111111", amount=750, status="SUCCESS", checkout_request_id="R1")
        b.transition("COMPLETED")
        self.assertEqual(Referral.objects.get().status, "REWARDED")
        self.assertEqual(DiamondEntry.objects.filter(user=self.other, kind="REFERRAL").count(), 1)

    def test_no_reward_without_successful_payment(self):
        Referral.objects.create(referrer=self.other, referee=self.cust)
        self.make_booking(status="CONFIRMED").transition("COMPLETED")
        self.assertEqual(Referral.objects.get().status, "PENDING")
