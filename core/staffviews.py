from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

staff_only = staff_member_required(login_url="/accounts/login/")


@staff_only
def overview(request):
    from bookings.models import Booking, PaymentAttempt, Refund
    from marketplace.models import Business
    from payouts.models import Payout
    from rewards.models import Withdrawal
    from subscriptions.models import Subscription
    from support.models import SupportTicket
    from verification.models import ProviderVerification
    from .models import AuditEvent
    u, now = request.user, timezone.now()
    st = {x["status"]: x["n"] for x in Business.objects.values("status").annotate(n=Count("id"))}
    by_status = list(Booking.objects.filter(created_at__gte=now - timedelta(days=30))
                     .values("status").annotate(n=Count("id")).order_by("-n"))
    top = max([x["n"] for x in by_status] or [1])
    for x in by_status:
        x["pct"] = max(4, int(x["n"] * 100 / top))
    ctx = {"providers": sum(st.values()), "approved": st.get("APPROVED", 0), "pending_providers": st.get("PENDING", 0),
           "active_subs": Subscription.objects.filter(period_end__gt=now).exclude(status="CANCELLED").count(),
           "by_status": by_status, "open_tickets": SupportTicket.objects.exclude(status="RESOLVED").count(),
           "events": AuditEvent.objects.select_related("actor")[:10]}
    if u.has_perm("verification.review_verification"):
        ctx["pending_verifications"] = ProviderVerification.objects.filter(status="PENDING").count()
    if u.has_perm("payouts.approve_payout"):  # money figures only for finance staff
        ok = [Booking.Status.CONFIRMED, Booking.Status.COMPLETED]
        ctx["money"] = {
            "deposits": Booking.objects.filter(status__in=ok).aggregate(s=Sum("deposit_amount"))["s"] or 0,
            "recon": PaymentAttempt.objects.filter(status="RECONCILIATION_REQUIRED").count(),
            "refunds": Refund.objects.filter(status="REQUESTED").count(),
            "payouts": Payout.objects.filter(status="REQUESTED").count(),
            "withdrawals": Withdrawal.objects.filter(status="REQUESTED").count()}
    return render(request, "core/staff_overview.html", ctx)


@staff_only
def verifications(request):
    from verification.models import ProviderVerification
    if not request.user.has_perm("verification.review_verification"):
        raise PermissionDenied
    status = request.GET.get("status", "PENDING")
    if status not in ("PENDING", "APPROVED", "REJECTED"):
        status = "PENDING"
    counts = {x["status"]: x["n"] for x in ProviderVerification.objects.values("status").annotate(n=Count("id"))}
    rows = ProviderVerification.objects.filter(status=status).select_related("business__owner").order_by("submitted_at")[:100]
    return render(request, "core/staff_verifications.html", {
        "rows": rows, "status": status, "counts": counts, "tabs": ["PENDING", "APPROVED", "REJECTED"]})
