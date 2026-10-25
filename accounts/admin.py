from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "phone_verified", "rewards_frozen")
    list_filter = ("phone_verified", "rewards_frozen")
    search_fields = ("user__email", "phone", "referral_code")
    readonly_fields = ("user", "phone", "phone_verified", "referral_code")
