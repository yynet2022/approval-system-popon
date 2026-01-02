from django.contrib import admin

from .models import (
    ApprovalLog,
    Approver,
)
from .models.types import (
    LocalBusinessTripRequest,
    SimpleRequest,
)


class ApproverInline(admin.TabularInline):
    model = Approver
    extra = 0
    ordering = ("order",)


class ApprovalLogInline(admin.TabularInline):
    model = ApprovalLog
    extra = 0
    ordering = ("created_at",)
    readonly_fields = ("created_at", "actor", "action", "step", "comment")

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SimpleRequest)
class SimpleRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "title",
        "applicant",
        "status",
        "current_step",
        "submitted_at",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "request_number",
        "title",
        "applicant__last_name",
        "applicant__first_name",
        "applicant__email",
    )
    inlines = [ApproverInline, ApprovalLogInline]
    readonly_fields = ("request_number", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("applicant")


@admin.register(LocalBusinessTripRequest)
class LocalBusinessTripRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "title",
        "trip_date",
        "destination",
        "applicant",
        "status",
        "current_step",
        "submitted_at",
    )
    list_filter = ("status", "trip_date", "created_at")
    search_fields = (
        "request_number",
        "title",
        "destination",
        "applicant__last_name",
        "applicant__first_name",
        "applicant__email",
    )
    inlines = [ApproverInline, ApprovalLogInline]
    readonly_fields = ("request_number", "created_at", "updated_at")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("applicant")


@admin.register(Approver)
class ApproverAdmin(admin.ModelAdmin):
    list_display = (
        "request_display",
        "order",
        "user",
        "status",
        "processed_at",
    )
    list_filter = ("status", "processed_at")
    search_fields = (
        "request__request_number",
        "user__last_name",
        "user__first_name",
        "user__email",
    )

    @admin.display(description="申請番号")
    def request_display(self, obj):
        return obj.request.request_number


@admin.register(ApprovalLog)
class ApprovalLogAdmin(admin.ModelAdmin):
    list_display = (
        "request_display",
        "action",
        "actor",
        "step",
        "created_at",
    )
    list_filter = ("action", "created_at")
    search_fields = (
        "request__request_number",
        "actor__last_name",
        "actor__first_name",
        "actor__email",
        "comment",
    )
    readonly_fields = (
        "request",
        "actor",
        "action",
        "step",
        "comment",
        "created_at",
        "updated_at",
    )

    @admin.display(description="申請番号")
    def request_display(self, obj):
        return obj.request.request_number

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
