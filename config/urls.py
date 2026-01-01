from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("notifications/", include("notification.urls")),
    path("approvals/", include("approvals.urls")),
    path("", include("portal.urls")),
]
