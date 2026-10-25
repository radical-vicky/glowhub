from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from accounts.services import get_profile
from core.services import rate_limit
from .models import Referral
from .services import balance, request_withdrawal


@login_required
@rate_limit("withdraw", 3)
def dashboard(request):
    p = get_profile(request.user)
    if request.method == "POST":
        try:
            request_withdrawal(request.user, request.POST.get("diamonds", "0"))
            messages.success(request, "Withdrawal requested. We review it before sending to M-Pesa.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("rewards")
    bal, per = balance(request.user), settings.REWARDS["DIAMONDS_PER_KES"]
    return render(request, "rewards/dashboard.html", {
        "p": p, "bal": bal, "kes": bal["available"] // per, "per": per, "r": settings.REWARDS,
        "link": request.build_absolute_uri(f"/?ref={p.referral_code}"),
        "entries": request.user.diamond_entries.order_by("-created_at")[:30],
        "withdrawals": request.user.withdrawals.order_by("-requested_at")[:5],
        "refs": Referral.objects.filter(referrer=request.user).count(),
        "open": settings.WITHDRAWALS_ENABLED})
