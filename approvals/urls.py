from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    path("create/", views.RequestCreateView.as_view(), name="create"),
    path("<uuid:pk>/", views.RequestDetailView.as_view(), name="detail"),
    path(
        "<uuid:pk>/action/",
        views.RequestActionView.as_view(),
        name="action"
    ),
    path(
        "<uuid:pk>/withdraw/",
        views.RequestWithdrawView.as_view(),
        name="withdraw"
    ),
    path(
        "<uuid:pk>/update/",
        views.RequestUpdateView.as_view(),
        name="update"
    ),
    path(
        "<uuid:pk>/proxy-remand/",
        views.RequestProxyRemandView.as_view(),
        name="proxy-remand"
    ),
]
