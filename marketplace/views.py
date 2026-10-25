from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Min, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from bookings.models import Booking
import csv, math
from django.contrib import messages
from django.http import HttpResponse
from bookings.models import Booking as _B
from core.services import audit
from subscriptions.services import can, can_add_service, require_feature, start_trial
from .forms import BlockForm, BusinessEditForm, BusinessForm, HoursFormSet, ReviewForm, ServiceForm
from .models import Review
from .models import Business, Category


def public_businesses():
    return (Business.objects.filter(status=Business.Status.APPROVED)
            .prefetch_related("photos")
            .annotate(avg_rating=Avg("reviews__rating", filter=Q(reviews__is_hidden=False)),
                      n_reviews=Count("reviews", filter=Q(reviews__is_hidden=False), distinct=True),
                      from_price=Min("services__price", filter=Q(services__is_active=True))))


def home(request):
    cats = list(Category.objects.all())
    return render(request, "marketplace/home.html", {
        "categories": cats,
        "featured": public_businesses().order_by("-avg_rating")[:5]})


def search(request):
    qs = public_businesses()
    q = request.GET.get("q", "").strip()[:80]
    area = request.GET.get("area", "").strip()[:80]
    cat = request.GET.get("category", "")
    try:
        max_price = int(request.GET.get("max_price", ""))
    except ValueError:
        max_price = None
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(services__name__icontains=q)).distinct()
    if area:
        qs = qs.filter(area__icontains=area)
    if cat:
        qs = qs.filter(categories__slug=cat)
    if max_price:
        qs = qs.filter(from_price__lte=max_price)
    results = list(qs.order_by("-avg_rating")[:200])
    try:
        lat, lng = float(request.GET["lat"]), float(request.GET["lng"])
        km = min(float(request.GET.get("km", 10)), 100)
        for b in results:
            b.distance = _km(lat, lng, b.latitude, b.longitude) if b.latitude is not None and b.longitude is not None else None
        results = sorted([b for b in results if b.distance is not None and b.distance <= km], key=lambda b: b.distance)
    except (KeyError, ValueError):
        pass
    results = results[:50]
    return render(request, "marketplace/search.html", {
        "results": results, "categories": Category.objects.all(),
        "q": q, "area": area, "cat": cat})


def provider_page(request, slug):
    b = get_object_or_404(public_businesses(), slug=slug)
    return render(request, "marketplace/provider.html", {
        "b": b, "services": b.services.filter(is_active=True),
        "reviews": b.reviews.filter(is_hidden=False)[:10],
        "map": _map_url(b),
        "hours": b.hours.order_by("weekday")})


@login_required
def become_provider(request):
    if hasattr(request.user, "business"):
        return redirect("dashboard")
    form = BusinessForm(request.POST or None)
    if form.is_valid():
        biz = form.save(commit=False)
        biz.owner = request.user
        biz.full_clean(exclude=["owner"])
        biz.save()
        form.save_m2m()
        start_trial(biz)
        audit(request.user, "business.created", biz.pk)
        return redirect("dashboard")
    return render(request, "marketplace/form.html", {
        "form": form, "title": "Set up your business",
        "hint": "We review every new provider before listing it."})


@login_required
def dashboard(request):
    biz = getattr(request.user, "business", None)
    now = timezone.now()
    if biz:
        bookings = biz.bookings.select_related("service", "customer")
        paid = bookings.filter(status=Booking.Status.CONFIRMED)
        return render(request, "marketplace/provider_dashboard.html", {
            "b": biz, "upcoming": paid.filter(start__gte=now).order_by("start")[:10],
            "pending": bookings.filter(status=Booking.Status.PENDING_PAYMENT).count(),
            "reviews": biz.reviews.order_by("-created_at")[:5],
            "deposits": sum(x.deposit_amount for x in paid)})
    mine = Booking.objects.filter(customer=request.user).select_related("business", "service")
    return render(request, "marketplace/customer_dashboard.html", {
        "upcoming": mine.filter(start__gte=now, status=Booking.Status.CONFIRMED).order_by("start"),
        "past": mine.filter(start__lt=now).order_by("-start")[:10]})


def _provider_only(request):
    biz = getattr(request.user, "business", None)
    if not biz:
        raise Http404
    return biz


@login_required
def services_list(request):
    biz = _provider_only(request)
    return render(request, "marketplace/services.html", {"services": biz.services.all(), "b": biz})


@login_required
def service_create(request):
    biz = _provider_only(request)
    if not can_add_service(biz):
        messages.error(request, "Your plan's service limit is reached or your plan has expired. Upgrade to add more.")
        return redirect("subscription")
    form = ServiceForm(request.POST or None)
    if form.is_valid():
        s = form.save(commit=False)
        s.business = biz
        s.save()
        return redirect("services")
    return render(request, "marketplace/form.html", {"form": form, "title": "Add a service"})


def _km(lat1, lng1, lat2, lng2):
    lat2, lng2 = float(lat2), float(lng2)
    p = math.pi / 180
    a = (0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lng2 - lng1) * p)) / 2)
    return 12742 * math.asin(math.sqrt(a))


@login_required
def profile_edit(request):
    biz = _provider_only(request)
    form = BusinessEditForm(request.POST or None, request.FILES or None, instance=biz)
    if form.is_valid():
        form.save()
        audit(request.user, "business.updated", biz.pk)
        messages.success(request, "Saved.")
        return redirect("dashboard")
    return render(request, "marketplace/form.html", {"form": form, "title": "Business details",
                  "hint": "Latitude/longitude: right-click your location in OpenStreetMap or Google Maps and copy the numbers."})


@login_required
def hours_edit(request):
    biz = _provider_only(request)
    fs = HoursFormSet(request.POST or None, instance=biz)
    if fs.is_valid():
        fs.save()
        return redirect("dashboard")
    return render(request, "marketplace/hours.html", {"fs": fs})


@login_required
def block_create(request):
    biz = _provider_only(request)
    form = BlockForm(request.POST or None)
    if form.is_valid():
        blk = form.save(commit=False)
        blk.business = biz
        blk.save()
        messages.success(request, "Time blocked.")
        return redirect("dashboard")
    return render(request, "marketplace/form.html", {"form": form, "title": "Block time (leave, break, holiday)"})


@login_required
def review_create(request, booking_id):
    b = get_object_or_404(_B, pk=booking_id, customer=request.user, status="COMPLETED")  # verified-service only
    if hasattr(b, "review"):
        return redirect("dashboard")
    form = ReviewForm(request.POST or None)
    if form.is_valid():
        r = form.save(commit=False)
        r.booking, r.business = b, b.business
        r.save()
        try:
            from rewards.services import on_review
            on_review(request.user, b)
        except Exception:
            pass
        return redirect("provider", b.business.slug)
    return render(request, "marketplace/form.html", {"form": form, "title": f"Review {b.business.name}"})


@login_required
def review_reply(request, review_id):
    r = get_object_or_404(Review, pk=review_id, business__owner=request.user)
    if request.method == "POST":
        r.provider_reply = request.POST.get("reply", "")[:1000]
        r.save(update_fields=["provider_reply"])
        return redirect("dashboard")
    return render(request, "marketplace/reply.html", {"r": r})


@login_required
def reports(request):
    biz = _provider_only(request)
    require_feature(biz, "reports_enabled")  # server-side entitlement
    qs = biz.bookings.all()
    S = _B.Status
    confirmed = qs.filter(status__in=[S.CONFIRMED, S.COMPLETED])
    if request.GET.get("format") == "csv":
        audit(request.user, "report.exported", biz.pk)
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="bookings.csv"'
        w = csv.writer(resp)
        w.writerow(["id", "start", "service", "customer", "status", "price", "deposit"])
        for b in qs.order_by("start"):
            safe = lambda v: "'" + v if str(v)[:1] in "=+-@" else v  # CSV-injection guard
            w.writerow([b.pk, b.start.isoformat(), safe(b.service_name), safe(b.contact_name), b.status, b.price, b.deposit_amount])
        return resp
    by_service = (confirmed.values("service_name").annotate(n=Count("id")).order_by("-n")[:5])
    return render(request, "marketplace/reports.html", {
        "total": qs.count(), "by_status": qs.values("status").annotate(n=Count("id")),
        "deposits_confirmed": sum(b.deposit_amount for b in confirmed),
        "deposits_pending": sum(b.deposit_amount for b in qs.filter(status=S.PENDING_PAYMENT)),
        "by_service": by_service})


def _map_url(b):
    if not (b.show_exact_location and b.latitude is not None and b.longitude is not None):
        return None
    lat, lng = float(b.latitude), float(b.longitude)
    d = 0.005
    return {"embed": f"https://www.openstreetmap.org/export/embed.html?bbox={lng-d},{lat-d},{lng+d},{lat+d}&layer=mapnik&marker={lat},{lng}",
            "directions": f"https://www.google.com/maps/dir/?api=1&destination={lat},{lng}"}
