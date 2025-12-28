from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    # 申請作成 (タイプ別)
    path(
        "create/simple/",
        views.SimpleRequestCreateView.as_view(),
        name="create_simple"
    ),
    path(
        "create/trip/",
        views.LocalBusinessTripRequestCreateView.as_view(),
        name="create_trip"
    ),

    # 共通処理 (詳細、アクション、更新、取り下げ、代理差戻し)
    # ※Requestモデルベースで動作する
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
