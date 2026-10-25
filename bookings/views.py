import json
import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from marketplace.models import Business, Service
from . import mpesa
from .availability import availability, slots_for
from accounts.decorators import phone_verified_required
from .forms import BookingForm
from .models import Booking, PaymentAttempt
from .payments import handle_callback, request_refund
from core.services import audit, notify, rate_limit

log = logging.getLogger(__name__)


def deposit_for(price, percent):
    return (price * percent / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)  # whole KES


@login_required
@rate_limit("book", 20)
@phone_verified_required("REQUIRE_PHONE_FOR_BOOKING")
def book_service(request, service_id):
    service = get_object_or_404(Service.objects.select_related("business"), pk=service_id,
                                is_active=True, business__status=Business.Status.APPROVED)
    biz = service.business
    try:
        day = date.fromisoformat(request.GET.get("date") or request.POST.get("date", ""))
    except ValueError:
        day = timezone.localdate()
    branches = list(biz.branches.filter(is_active=True))
    branch = next((x for x in branches if str(x.pk) == (request.GET.get("branch") or request.POST.get("branch"))), None)
    if branch is None and len(branches) == 1:
        branch = branches[0]
    slots = slots_for(service, day, branch) if (branch or not branches) else []
    form = BookingForm(request.POST or None, initial={
        "contact_name": request.user.get_full_name()})
    deposit = deposit_for(service.price, biz.deposit_percent)

    if request.method == "POST" and form.is_valid():
        slot = form.cleaned_data["slot"]
        with transaction.atomic():
            Business.objects.select_for_update().get(pk=biz.pk)  # serialize per business
            start = timezone.localtime(slot)
            res = availability(service, start.date(), branch).get(start) if (branch or not branches) else None
            if res is None:
                form.add_error("slot", "That time was just taken. Please pick another.")
            else:
                booking = Booking.objects.create(
                    customer=request.user, business=biz, service=service, start=start,
                    staff=res[0], branch=res[1],
                    end=start + timedelta(minutes=service.duration_minutes),
                    expires_at=timezone.now() + timedelta(minutes=settings.PENDING_PAYMENT_MINUTES),
                    service_name=service.name, price=service.price, deposit_amount=deposit,
                    duration_minutes=service.duration_minutes, policy_snapshot=biz.cancellation_policy,
                    contact_name=form.cleaned_data["contact_name"],
                    contact_phone=form.cleaned_data["contact_phone"],
                    notes=form.cleaned_data["notes"])
                return redirect("pay", booking.pk)

    return render(request, "bookings/book.html", {
        "service": service, "b": biz, "day": day, "branches": branches, "branch": branch, "slots": slots, "form": form, "deposit": deposit,
        "balance": service.price - deposit,
        "days": [timezone.localdate() + timedelta(days=i) for i in range(7)]})


@login_required
@rate_limit("pay", 6)
def pay(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, customer=request.user)  # ownership check
    error = None
    if booking.status == Booking.Status.CONFIRMED:
        return redirect("confirmation", booking.pk)
    if request.method == "POST" and booking.status == Booking.Status.PENDING_PAYMENT:
        if booking.expires_at and booking.expires_at < timezone.now():
            error = "This reservation expired. Please choose a time again."
        else:
            try:
                phone = mpesa.normalize_phone(request.POST.get("phone", booking.contact_phone))
                attempt = PaymentAttempt.objects.create(
                    booking=booking, phone=phone, amount=booking.deposit_amount)  # amount from DB only
                resp = mpesa.stk_push(phone, booking.deposit_amount, f"BK{booking.pk}", "Deposit")
                attempt.checkout_request_id = resp.get("CheckoutRequestID")
                attempt.merchant_request_id = resp.get("MerchantRequestID", "")
                attempt.status = PaymentAttempt.Status.PENDING
                attempt.save()
                return redirect("pay_status", booking.pk)
            except ValueError as e:
                error = str(e)
            except Exception:
                log.exception("STK push failed")
                error = "We couldn't reach M-Pesa. Please try again in a moment."
    return render(request, "bookings/pay.html", {"booking": booking, "error": error})


@login_required
def pay_status(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, customer=request.user)
    if request.GET.get("json"):
        return JsonResponse({"status": booking.status})
    if booking.status == Booking.Status.CONFIRMED:
        return redirect("confirmation", booking.pk)
    return render(request, "bookings/pay_status.html", {"booking": booking})


@login_required
def confirmation(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, customer=request.user,
                                status=Booking.Status.CONFIRMED)
    return render(request, "bookings/confirmation.html", {"booking": booking})


@login_required
@require_POST
def cancel(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, customer=request.user)
    if booking.status == Booking.Status.CONFIRMED and booking.start - timezone.now() > timedelta(hours=24):
        booking.transition(Booking.Status.CANCELLED_BY_CUSTOMER, actor=request.user)
        request_refund(booking, "Customer cancelled with more than 24h notice", request.user)
        notify(booking.business.owner, "Booking cancelled", f"{booking.contact_name} cancelled {booking.service_name} on {booking.start:%d %b %H:%M}.")
    return redirect("dashboard")


@csrf_exempt
@require_POST
def mpesa_callback(request, secret):
    if secret != settings.MPESA["CALLBACK_SECRET"]:
        return HttpResponse(status=404)
    try:
        handle_callback(json.loads(request.body))
    except Exception:
        log.exception("Callback processing failed")
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@login_required
def provider_bookings(request):
    biz = getattr(request.user, "business", None)
    if not biz:
        raise Http404
    qs = biz.bookings.exclude(status__in=["PENDING_PAYMENT", "EXPIRED"]).select_related("service").order_by("-start")[:100]
    return render(request, "bookings/provider_list.html", {"bookings": qs, "now": timezone.now()})


@login_required
@require_POST
def provider_action(request, booking_id, action):
    booking = get_object_or_404(Booking, pk=booking_id, business__owner=request.user)  # ownership
    S = Booking.Status
    try:
        if action in ("complete", "no_show") and booking.start <= timezone.now():
            booking.transition(S.COMPLETED if action == "complete" else S.NO_SHOW, actor=request.user)
        elif action == "cancel":
            booking.transition(S.CANCELLED_BY_PROVIDER, actor=request.user)
            request_refund(booking, "Cancelled by provider: full refund", request.user)
            notify(booking.customer, "Your booking was cancelled", f"{booking.business.name} cancelled {booking.service_name}. Your deposit will be refunded in full.", urgent=True)
        audit(request.user, f"booking.{action}", booking.pk)
    except ValueError:
        pass
    return redirect("provider_bookings")
