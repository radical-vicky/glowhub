from django.contrib import admin
from .models import Subscription, SubscriptionPayment, SubscriptionPlan
admin.site.register(SubscriptionPlan, list_display=("name", "price", "max_services", "inventory_enabled", "reports_enabled", "is_active"))
admin.site.register(Subscription, list_display=("business", "plan", "status", "period_end"), list_filter=("status", "plan"))
admin.site.register(SubscriptionPayment, list_display=("subscription", "plan", "amount", "status", "created_at"), list_filter=("status",))
