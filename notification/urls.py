from django.urls import path

from . import views

app_name = "notification"

urlpatterns = [
    path("<uuid:pk>/", views.NotificationDetailView.as_view(), name="detail"),
]
