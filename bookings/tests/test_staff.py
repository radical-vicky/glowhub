from datetime import timedelta
from django.utils import timezone

from bookings.availability import availability
from bookings.models import Booking
from bookings.tests.test_core import Base
from marketplace.models import Staff, StaffHours
from datetime import time


class StaffAvailability(Base):
    def _book(self, start, staff):
        return Booking.objects.create(
            customer=self.cust, business=self.biz, service=self.svc, staff=staff, start=start,
            end=start + timedelta(minutes=90), status="CONFIRMED", service_name="B", price=1500,
            deposit_amount=750, duration_minutes=90, policy_snapshot="p", contact_name="C", contact_phone="254712345678")

    def _two_staff(self):
        a, b = (Staff.objects.create(business=self.biz, name=n) for n in "AB")
        a.services.add(self.svc)
        b.services.add(self.svc)
        return a, b

    def test_second_staff_keeps_slot_open_until_both_busy(self):
        a, b = self._two_staff()
        start = min(availability(self.svc, self.day))
        self._book(start, a)
        free = availability(self.svc, self.day)
        self.assertIn(start, free)
        self.assertEqual(free[start][0], b)
        self._book(start, b)
        self.assertNotIn(start, availability(self.svc, self.day))

    def test_staff_own_hours_override_business_hours(self):
        a, _ = self._two_staff()
        a.is_active = False
        a.save()
        b = Staff.objects.get(name="B")
        other_day = (self.day.weekday() + 1) % 7
        StaffHours.objects.create(staff=b, weekday=other_day, opens=time(9), closes=time(17))
        self.assertEqual(availability(self.svc, self.day), {})
