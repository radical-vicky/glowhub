from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from core.services import rate_limit
from .services import get_profile, send_otp, verify_otp


@login_required
@rate_limit("otp", 10)
def phone(request):
    p, error = get_profile(request.user), None
    stage = "verify" if request.session.get("otp_sent") else "enter"
    if request.method == "POST":
        a = request.POST.get("action")
        try:
            if a == "send":
                send_otp(request.user, request.POST.get("phone", ""))
                request.session["otp_sent"], stage = True, "verify"
            elif a == "verify":
                verify_otp(request.user, request.POST.get("code", "").strip())
                request.session.pop("otp_sent", None)
                messages.success(request, "Phone number verified.")
                nxt = request.GET.get("next", "")
                return redirect(nxt if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}) else "dashboard")
            elif a == "prefs":
                p.sms_opt_in = "sms" in request.POST
                p.whatsapp_opt_in = "whatsapp" in request.POST
                p.marketing_opt_in = "marketing" in request.POST
                p.save()
                messages.success(request, "Preferences saved.")
            elif a == "restart":
                request.session.pop("otp_sent", None)
                stage = "enter"
        except ValueError as e:
            error = str(e)
    return render(request, "accounts/phone.html", {"p": p, "stage": stage, "error": error})
