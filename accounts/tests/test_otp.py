import re
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from accounts.services import get_profile, send_otp, verify_otp

U = get_user_model()


class OTP(TestCase):
    def setUp(self):
        self.u = U.objects.create_user("a", "a@x.com", "pw")

    def _send(self, phone="0712345678"):
        with patch("accounts.services.send_sms") as m:
            send_otp(self.u, phone)
        return re.search(r"\d{6}", m.call_args[0][1]).group()

    def test_correct_code_verifies(self):
        verify_otp(self.u, self._send())
        p = get_profile(self.u)
        self.assertTrue(p.phone_verified)
        self.assertEqual(p.phone, "254712345678")

    def test_wrong_code_rejected(self):
        self._send()
        with self.assertRaises(ValueError):
            verify_otp(self.u, "000000")

    def test_number_cannot_be_shared(self):
        verify_otp(self.u, self._send())
        other = U.objects.create_user("b", "b@x.com", "pw")
        with self.assertRaises(ValueError):
            send_otp(other, "0712345678")
