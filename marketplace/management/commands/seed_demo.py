from datetime import time
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from marketplace.models import Business, BusinessHours, Category, Service


class Command(BaseCommand):
    help = "Create demo categories and one approved provider"

    def handle(self, *a, **kw):
        cats = {n: Category.objects.get_or_create(name=n, slug=n.lower().replace(" & ", "-").replace(" ", "-"))[0]
                for n in ["Hair & Wigs", "Nails", "Skincare", "Massage", "Spa & Wellness", "Makeup", "Barbers"]}
        U = get_user_model()
        u, _ = U.objects.get_or_create(username="demo", defaults={"email": "demo@example.com"})
        u.set_password("demo12345")
        u.save()
        b, _ = Business.objects.get_or_create(owner=u, defaults=dict(
            name="Luxe Beauty Studio", slug="luxe-beauty", area="Westlands, Nairobi",
            description="Premium braids, styling and treatments.",
            status="APPROVED", verified=True))
        b.categories.add(cats["Hair & Wigs"])
        from subscriptions.services import ensure_plans, start_trial
        ensure_plans()
        if not hasattr(b, "subscription"):
            start_trial(b)
        for d in range(6):
            BusinessHours.objects.get_or_create(business=b, weekday=d, defaults=dict(opens=time(9), closes=time(18)))
        for n, p, m in [("Braids (Medium)", 1500, 90), ("Silk Press", 2000, 60), ("Hair Treatment", 2000, 120)]:
            Service.objects.get_or_create(business=b, name=n, defaults=dict(price=p, duration_minutes=m))
        self.stdout.write("Seeded. Demo provider login: demo / demo12345 (email login required via allauth; use admin to set verified email)")
