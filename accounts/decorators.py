from functools import wraps
from urllib.parse import quote
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from .services import get_profile


def phone_verified_required(setting=None):
    def deco(view):
        @wraps(view)
        def w(request, *a, **kw):
            enforced = getattr(settings, setting, True) if setting else True
            if enforced and request.user.is_authenticated and not get_profile(request.user).phone_verified:
                return redirect(f"{reverse('phone')}?next={quote(request.get_full_path())}")
            return view(request, *a, **kw)
        return w
    return deco
