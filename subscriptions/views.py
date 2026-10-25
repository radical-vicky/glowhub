import json
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from bookings import mpesa
from core.services import audit, rate_limit
from .models import SubscriptionPayment, SubscriptionPlan
from .services import ensure_plans, handle_subscription_callback

log = logging.getLogger(__name__)


@login_required
@rate_limit("subscribe", 5)
def plans(request):
    biz = getattr(request.user, "business", None)
    if not biz:
        raise Http404
    ensure_plans()
    error = None
    if request.method == "POST":
        try:
            plan = SubscriptionPlan.objects.get(pk=request.POST.get("plan"), is_active=True)
            phone = mpesa.normalize_phone(request.POST.get("phone", biz.phone))
            sub = biz.subscription
            pay = SubscriptionPayment.objects.create(subscription=sub, plan=plan, amount=plan.price, phone=phone)
            resp = mpesa.stk_push(phone, plan.price, f"SUB{pay.pk}", "Subscription",
                                  callback_path="subscription/mpesa/callback")
            pay.checkout_request_id = resp.get("CheckoutRequestID")
            pay.save()
            audit(request.user, "subscription.payment_started", biz.pk, plan=plan.name)
            return render(request, "subscriptions/pending.html", {"plan": plan})
        except (ValueError, SubscriptionPlan.DoesNotExist) as e:
            error = str(e) or "Choose a plan."
        except Exception:
            log.exception("Subscription STK failed")
            error = "We couldn't reach M-Pesa. Please try again."
    return render(request, "subscriptions/plans.html", {
        "plans": SubscriptionPlan.objects.filter(is_active=True), "sub": biz.subscription,
        "history": biz.subscription.payments.order_by("-created_at")[:10], "error": error})


@csrf_exempt
@require_POST
def callback(request, secret):
    if secret != settings.MPESA["CALLBACK_SECRET"]:
        return HttpResponse(status=404)
    try:
        handle_subscription_callback(json.loads(request.body))
    except Exception:
        log.exception("Subscription callback failed")
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
