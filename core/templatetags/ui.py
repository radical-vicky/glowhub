from django import template

register = template.Library()
OK = {"CONFIRMED", "COMPLETED", "SUCCESS", "PAID", "APPROVED", "ACTIVE", "SENT", "RESOLVED", "REWARDED"}
WARN = {"PENDING", "PENDING_PAYMENT", "REQUESTED", "PROCESSING", "IN_REVIEW", "RESCHEDULE_REQUESTED", "OPEN", "TRIAL", "REFUND_PENDING"}
BAD = {"CANCELLED_BY_CUSTOMER", "CANCELLED_BY_PROVIDER", "NO_SHOW", "FAILED", "REJECTED", "EXPIRED", "REVERSED"}


@register.filter
def pillclass(value):
    v = str(value)
    return "ok" if v in OK else "warn" if v in WARN else "bad" if v in BAD else ""


@register.filter
def cdn(url, transform=""):
    """Add Cloudinary resize/crop options, e.g. {{ photo.image.url|cdn:"w_600,h_400,c_fill" }}."""
    url = str(url or "")
    if transform and "res.cloudinary.com" in url and "/upload/" in url:
        return url.replace("/upload/", f"/upload/{transform}/", 1)
    return url
