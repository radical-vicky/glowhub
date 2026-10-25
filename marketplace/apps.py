from django.apps import AppConfig
from django.db.models.signals import post_migrate

DEFAULT_CATEGORIES = [("Hair & Wigs", "hair-wigs"), ("Nails", "nails"), ("Skincare", "skincare"), ("Massage", "massage"),
                      ("Spa & Wellness", "spa-wellness"), ("Makeup", "makeup"), ("Barbers", "barbers")]


def create_categories(sender, **kwargs):
    from django.apps import apps
    Category = apps.get_model("marketplace", "Category")
    for name, slug in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(slug=slug, defaults={"name": name})


class MarketplaceConfig(AppConfig):
    name = "marketplace"

    def ready(self):
        post_migrate.connect(create_categories, sender=self)
