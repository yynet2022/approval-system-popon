from django.contrib import admin

from .models import LoginToken, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "last_name",
        "first_name",
        "is_staff",
        "is_approver",
        "is_active",
    )
    search_fields = ("email", "last_name", "first_name")


@admin.register(LoginToken)
class LoginTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "token", "expires_at", "created_at")
    readonly_fields = ("created_at", "updated_at")
