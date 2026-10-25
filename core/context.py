from django.conf import settings


def assets(request):
    """Version query string so browsers never keep serving a stale stylesheet."""
    try:
        v = max(int(p.stat().st_mtime) for p in (settings.BASE_DIR / "static").rglob("*") if p.is_file())
    except (OSError, ValueError):
        v = 1
    return {"ASSET_V": v}


def site(request):
    from .models import SiteSettings
    try:
        return {"SITE": SiteSettings.current()}
    except Exception:  # table not created yet (before migrate)
        return {"SITE": None}
