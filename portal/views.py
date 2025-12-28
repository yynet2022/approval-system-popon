from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.utils import timezone
from django.views.generic import TemplateView
from django.shortcuts import render

from approvals.models import Approver, Request
from notification.models import Notification
from .forms import SearchForm


class DashboardView(TemplateView):
    """
    ポータル画面（ダッシュボード）。
    """
    template_name = "portal/index.html"

    def get_notifications(self):
        """お知らせ一覧を取得してページネーション"""
        qs = Notification.objects.filter(
            published_at__lte=timezone.now()
        ).order_by("-published_at")

        paginator = Paginator(qs, settings.PORTAL_NOTIFICATIONS_PER_PAGE)
        page_number = self.request.GET.get('n_page')
        return paginator.get_page(page_number)

    def get_requests(self, form):
        """申請一覧を取得してページネーション"""
        user = self.request.user

        # ベースのクエリセット作成 (全ての申請 Request を対象)
        if user.is_authenticated:
            my_related_ids = Request.objects.filter(
                Q(applicant=user) | Q(approvers__user=user)
            ).values_list("id", flat=True)

            qs = Request.objects.filter(
                Q(is_restricted=False) | Q(id__in=my_related_ids)
            )
        else:
            qs = Request.objects.filter(is_restricted=False)

        # 検索フィルタ適用
        if form.is_valid():
            q = form.cleaned_data.get("q")
            status = form.cleaned_data.get("status")
            applicant = form.cleaned_data.get("applicant")
            own_only = form.cleaned_data.get("own_only")

            if q:
                qs = qs.filter(
                    Q(title__icontains=q) | Q(request_number__icontains=q)
                )

            if status:
                qs = qs.filter(status=status)

            if user.is_authenticated and own_only:
                qs = qs.filter(applicant=user)
            elif applicant:
                qs = qs.filter(applicant=applicant)

        # 並び替え
        qs = qs.select_related("applicant").order_by("-submitted_at")

        paginator = Paginator(qs, settings.PORTAL_REQUESTS_PER_PAGE)
        page_number = self.request.GET.get('page')
        return paginator.get_page(page_number)

    def get(self, request, *args, **kwargs):
        # Ajaxリクエスト（ヘッダーで判断）
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            target = request.GET.get('target')
            form = SearchForm(request.GET)

            if target == 'notification':
                context = {'notifications': self.get_notifications()}
                template = "portal/partials/notification_list.html"
                return render(request, template, context)

            if target == 'request':
                context = {'request_list': self.get_requests(form)}
                template = "portal/partials/request_list.html"
                return render(request, template, context)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # 検索フォームの初期化
        form = SearchForm(self.request.GET)
        context["search_form"] = form

        # 1. お知らせ取得
        context["notifications"] = self.get_notifications()

        # 3. 全申請一覧
        context["request_list"] = self.get_requests(form)

        # 2. 承認依頼（ログイン時のみ）
        if user.is_authenticated:
            # 承認待ち (Approver と Request で絞り込み)
            context["pending_approvals"] = Request.objects.filter(
                status=Request.STATUS_PENDING,
                approvers__user=user,
                approvers__status=Approver.STATUS_PENDING,
                approvers__order=F("current_step")
            ).select_related("applicant").distinct().order_by("submitted_at")

            # 差戻し（再申請待ち）
            context["remanded_requests"] = Request.objects.filter(
                applicant=user,
                status=Request.STATUS_REMANDED
            ).order_by("-updated_at")

        return context
