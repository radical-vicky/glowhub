from datetime import datetime, time as dtime, timedelta
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from .models import Booking


def _active_bookings(business, start, end):
    S, now = Booking.Status, timezone.now()
    return list(Booking.objects.filter(business=business, start__lt=end, end__gt=start).filter(
        Q(status__in=[S.CONFIRMED, S.RESCHEDULE_REQUESTED]) | Q(status=S.PENDING_PAYMENT, expires_at__gt=now)))


def resources(service, branch=None):
    """Who can perform the service: active staff assigned to it, else the business itself."""
    staff = service.business.staff.filter(is_active=True, services=service)
    if branch:
        staff = staff.filter(Q(branch=branch) | Q(branch__isnull=True))
    staff = list(staff)
    return [(s, branch or s.branch) for s in staff] or [(None, branch)]


def _hours(staff, biz, weekday):
    if staff and staff.hours.exists():  # own schedule; no row for the day means day off
        return staff.hours.filter(weekday=weekday).first()
    return biz.hours.filter(weekday=weekday).first()


def availability(service, day, branch=None):
    """Server-side availability: {aware start datetime: (staff, branch)} for the first free resource."""
    biz, tz, now = service.business, timezone.get_current_timezone(), timezone.now()
    if day < now.astimezone(tz).date() or day > (now + timedelta(days=settings.BOOKING_HORIZON_DAYS)).date():
        return {}
    day_start = timezone.make_aware(datetime.combine(day, dtime.min), tz)
    day_end = day_start + timedelta(days=1)
    taken = _active_bookings(biz, day_start, day_end)
    blocks = list(biz.blocks.filter(start__lt=day_end, end__gt=day_start))
    buf = timedelta(minutes=biz.buffer_minutes)
    length = timedelta(minutes=service.duration_minutes)
    earliest = now + timedelta(hours=settings.MIN_ADVANCE_HOURS)
    out = {}
    for staff, br in resources(service, branch):
        hours = _hours(staff, biz, day.weekday())
        if not hours:
            continue
        open_dt = timezone.make_aware(datetime.combine(day, hours.opens), tz)
        close_dt = timezone.make_aware(datetime.combine(day, hours.closes), tz)
        mine = [b for b in taken if (b.staff_id == staff.pk if staff else
                                     (b.staff_id is None and (br is None or b.branch_id == br.pk)))]
        my_blocks = [k for k in blocks if k.staff_id is None or (staff and k.staff_id == staff.pk)]
        t = open_dt
        while t + length <= close_dt:
            if (t >= earliest and t not in out
                    and not any(b.start < t + length + buf and b.end + buf > t for b in mine)
                    and not any(k.start < t + length and k.end > t for k in my_blocks)):
                out[t] = (staff, br)
            t += timedelta(minutes=settings.SLOT_STEP_MINUTES)
    return out


def slots_for(service, day, branch=None):
    return sorted(availability(service, day, branch))
