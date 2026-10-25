from django.conf import settings
from django.shortcuts import redirect


class StaffMFAMiddleware:
    """Staff/admin accounts must enrol an authenticator app before using the admin."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = request.user
        if (not settings.DEBUG and u.is_authenticated and u.is_staff
                and not request.path.startswith(("/accounts/", "/static/"))):
            from allauth.mfa.utils import is_mfa_enabled
            if not is_mfa_enabled(u):
                return redirect("/accounts/2fa/")
        return self.get_response(request)


class SecurityHeadersMiddleware:
    CSP = ("default-src 'self'; img-src 'self' data: blob: https:; style-src 'self' 'unsafe-inline'; "
           "script-src 'self'; media-src 'self' blob:; frame-src https://www.openstreetmap.org; frame-ancestors 'none'; "
           "form-action 'self'; base-uri 'self'")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        r = self.get_response(request)
        if not request.path.startswith("/admin/"):
            r.headers.setdefault("Content-Security-Policy", self.CSP)
        r.headers.setdefault("Referrer-Policy", "same-origin")
        r.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(self), microphone=()")
        return r


class ReferralCaptureMiddleware:
    """Remember ?ref=CODE so it can be attached when the visitor signs up."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref = request.GET.get("ref", "")[:12]
        if ref.isalnum():
            request.session["ref"] = ref.upper()
        return self.get_response(request)
