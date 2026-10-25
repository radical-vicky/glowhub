import csv, json, logging
from decimal import InvalidOperation
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.services import audit, rate_limit
from .services import balances, handle_b2c_result, request_payout

log = logging.getLogger(__name__)


@login_required
@rate_limit("payout", 3)
def earnings(request):
    biz = getattr(request.user, "business", None)
    if not biz:
        raise Http404
    if request.method == "POST":
        try:
            request_payout(biz, request.POST.get("amount", ""), request.user)
            messages.success(request, "Payout requested. We review requests before sending.")
        except (ValueError, InvalidOperation) as e:
            messages.error(request, str(e) if isinstance(e, ValueError) else "Enter a valid amount.")
        return redirect("earnings")
    if request.GET.get("format") == "csv":
        audit(request.user, "statement.exported", biz.pk)
        r = HttpResponse(content_type="text/csv")
        r["Content-Disposition"] = 'attachment; filename="statement.csv"'
        w = csv.writer(r)
        w.writerow(["date", "type", "amount_kes", "note"])
        for e in biz.ledger.order_by("created_at"):
            w.writerow([e.created_at.isoformat(), e.kind, e.amount, e.note])
        return r
    return render(request, "payouts/earnings.html", {
        "b": biz, "bal": balances(biz), "ledger": biz.ledger.order_by("-created_at")[:30],
        "payouts": biz.payouts.order_by("-requested_at")[:10], "fee": settings.PLATFORM_FEE_PERCENT,
        "min": settings.MIN_PAYOUT_KES})


@csrf_exempt
@require_POST
def b2c_result(request, secret):
    if secret != settings.MPESA["CALLBACK_SECRET"]:
        return HttpResponse(status=404)
    try:
        handle_b2c_result(json.loads(request.body))
    except Exception:
        log.exception("B2C result failed")
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})


@csrf_exempt
@require_POST
def b2c_timeout(request, secret):
    if secret != settings.MPESA["CALLBACK_SECRET"]:
        return HttpResponse(status=404)
    log.warning("B2C timeout: %s", request.body[:500])  # stays PROCESSING; staff reconcile
    return JsonResponse({"ResultCode": 0, "ResultDesc": "Accepted"})
