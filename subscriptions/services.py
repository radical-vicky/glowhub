from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from .models import Subscription, SubscriptionPayment, SubscriptionPlan

DEFAULT_PLANS = [  # name, price, max_services, inventory, reports, staff, branches
    ("Starter", 500, 5, False, False, False, False),
    ("Growth", 1500, 50, True, True, False, False),
    ("Premium", 3000, 200, True, True, True, True),
]


def ensure_plans():
    for n, p, m, inv, rep, st, br in DEFAULT_PLANS:
        SubscriptionPlan.objects.get_or_create(name=n, defaults=dict(
            price=p, max_services=m, inventory_enabled=inv, reports_enabled=rep,
            staff_enabled=st, branches_enabled=br))


def start_trial(business):
    ensure_plans()
    return Subscription.objects.create(
        business=business, plan=SubscriptionPlan.objects.get(name="Premium"),
        status="TRIAL", period_end=timezone.now() + timedelta(days=settings.TRIAL_DAYS))


def current_plan(business):
    sub = getattr(business, "subscription", None)
    return sub.plan if sub and sub.entitled else None


def can(business, feature):
    plan = current_plan(business)
    return bool(plan and getattr(plan, feature, False))


def require_feature(business, feature):
    if not can(business, feature):
        raise Http404  # hidden rather than advertised; UI links to /subscription/ instead


def can_add_service(business):
    plan = current_plan(business)
    return bool(plan and business.services.filter(is_active=True).count() < plan.max_services)


@transaction.atomic
def handle_subscription_callback(payload):
    cb = payload.get("Body", {}).get("stkCallback", {})
    pay = (SubscriptionPayment.objects.select_for_update()
           .filter(checkout_request_id=cb.get("CheckoutRequestID")).select_related("subscription").first())
    if not pay or pay.status != "PENDING":
        return  # unknown or duplicate
    if cb.get("ResultCode") != 0:
        pay.status = "FAILED"
        pay.save()
        return
    items = {i["Name"]: i.get("Value") for i in cb.get("CallbackMetadata", {}).get("Item", [])}
    if Decimal(str(items.get("Amount", 0))) < pay.amount:
        pay.status = "FAILED"
        pay.save()
        return
    pay.status, pay.receipt = "SUCCESS", items.get("MpesaReceiptNumber")
    pay.save()
    sub = pay.subscription
    base = max(sub.period_end, timezone.now())
    sub.plan, sub.status = pay.plan, "ACTIVE"
    sub.period_end = base + timedelta(days=pay.plan.period_days)
    sub.save()
    try:
        from rewards.services import on_subscription_paid
        on_subscription_paid(sub.business)
    except Exception:
        pass
