from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bookings.models import Booking
from core.services import audit, notify, rate_limit
from .models import Message


def _booking(request, pk):
    b = get_object_or_404(Booking.objects.select_related("business__owner", "customer"), pk=pk)
    if request.user not in (b.customer, b.business.owner):  # participants only
        raise Http404
    if b.status in ("PENDING_PAYMENT", "EXPIRED"):
        raise Http404
    return b


@login_required
@rate_limit("message", 10)
def thread(request, booking_id):
    b = _booking(request, booking_id)
    if request.method == "POST":
        body = request.POST.get("body", "").strip()[:1000]
        if body:
            Message.objects.create(booking=b, sender=request.user, body=body)
            other = b.business.owner if request.user == b.customer else b.customer
            notify(other, "New message on GlowHub", "You have a new message about a booking. Log in to read and reply.")
        return redirect("thread", b.pk)
    return render(request, "messaging/thread.html", {"b": b, "messages_list": b.messages.select_related("sender")})


@login_required
@require_POST
def report(request, message_id):
    m = get_object_or_404(Message.objects.select_related("booking__business"), pk=message_id)
    _booking(request, m.booking_id)
    if m.sender_id != request.user.pk:
        m.reported = True
        m.save(update_fields=["reported"])
        audit(request.user, "message.reported", m.pk)
    return redirect("thread", m.booking_id)
