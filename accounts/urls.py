from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/sent/", views.LoginSentView.as_view(), name="login_sent"),
    path(
        "login/verify/<str:token>/",
        views.VerifyTokenView.as_view(),
        name="verify",
    ),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path(
        "approver-autocomplete/",
        views.ApproverAutocomplete.as_view(),
        name="approver-autocomplete",
    ),
    path(
        "active-user-autocomplete/",
        views.ActiveUserAutocomplete.as_view(),
        name="active-user-autocomplete",
    ),
]
