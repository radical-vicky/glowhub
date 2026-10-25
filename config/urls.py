from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from core import views as core, staffviews as staff
from marketplace import views as m, views_team as team
from accounts import views as acct

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/phone/", acct.phone, name="phone"),
    path("accounts/", include("allauth.urls")),
    path("robots.txt", core.robots),
    path("staff/", staff.overview, name="staff"),
    path("staff/verifications/", staff.verifications, name="staff_verifications"),
    path("legal/<str:page>/", core.legal, name="legal"),
    path("", m.home, name="home"),
    path("search/", m.search, name="search"),
    path("become-provider/", m.become_provider, name="become_provider"),
    path("dashboard/", m.dashboard, name="dashboard"),
    path("dashboard/profile/", m.profile_edit, name="profile_edit"),
    path("dashboard/hours/", m.hours_edit, name="hours"),
    path("dashboard/block/", m.block_create, name="block_create"),
    path("dashboard/reports/", m.reports, name="reports"),
    path("dashboard/services/", m.services_list, name="services"),
    path("dashboard/services/new/", m.service_create, name="service_create"),
    path("reviews/new/<int:booking_id>/", m.review_create, name="review_create"),
    path("reviews/<int:review_id>/reply/", m.review_reply, name="review_reply"),
    path("book/", include("bookings.urls")),
    path("inventory/", include("inventory.urls")),
    path("subscription/", include("subscriptions.urls")),
    path("messages/", include("messaging.urls")),
    path("support/", include("support.urls")),
    path("dashboard/team/", team.team, name="team"),
    path("dashboard/team/staff/new/", team.staff_edit, name="staff_new"),
    path("dashboard/team/staff/<int:pk>/", team.staff_edit, name="staff_edit"),
    path("dashboard/team/staff/<int:pk>/hours/", team.staff_hours, name="staff_hours"),
    path("dashboard/team/branch/new/", team.branch_edit, name="branch_new"),
    path("dashboard/team/branch/<int:pk>/", team.branch_edit, name="branch_edit"),
    path("dashboard/photos/", team.photos, name="photos"),
    path("dashboard/photos/<int:pk>/delete/", team.photo_delete, name="photo_delete"),
    path("verification/", include("verification.urls")),
    path("earnings/", include("payouts.urls")),
    path("rewards/", include("rewards.urls")),
    path("<slug:slug>/", m.provider_page, name="provider"),  # keep last
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
