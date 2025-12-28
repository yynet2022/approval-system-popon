from django.contrib import admin
from .models import SimpleRequest, SimpleApprover, SimpleApprovalLog


class SimpleApproverInline(admin.TabularInline):
    model = SimpleApprover
    extra = 0
    fields = ("user", "order", "status", "comment", "processed_at")


class SimpleApprovalLogInline(admin.TabularInline):
    model = SimpleApprovalLog
    extra = 0
    readonly_fields = ("actor", "action", "step", "comment", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SimpleRequest)
class SimpleRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number",
        "applicant",
        "title",
        "status",
        "current_step",
        "submitted_at"
    )
    list_filter = ("status", "is_restricted")
    search_fields = ("request_number", "title", "applicant__email")
    inlines = [SimpleApproverInline, SimpleApprovalLogInline]


@admin.register(SimpleApprover)
class SimpleApproverAdmin(admin.ModelAdmin):
    list_display = ("request", "user", "order", "status", "processed_at")
    list_filter = ("status",)


@admin.register(SimpleApprovalLog)
class SimpleApprovalLogAdmin(admin.ModelAdmin):
    list_display = ("request", "actor", "action", "created_at")
    readonly_fields = (
        "request",
        "actor",
        "action",
        "step",
        "comment",
        "created_at",
        "updated_at"
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
