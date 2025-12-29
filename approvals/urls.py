from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    # 汎用申請作成 (タイプ別)
    # create/simple/ -> request_type="simple"
    # create/trip/   -> request_type="trip"
    path(
        "create/<str:request_type>/",
        views.RequestCreateView.as_view(),
        name="create"
    ),

    # 共通処理
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
