import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import ActionForm, ApproverFormSet, RequestForm
from .models import SimpleApprovalLog, SimpleApprover, SimpleRequest
from .services import NotificationService

logger = logging.getLogger(__name__)


def save_approvers(request_obj, approvers_list):
    """
    承認者リストを保存するヘルパー関数。
    """
    for i, approver_user in enumerate(approvers_list, start=1):
        SimpleApprover.objects.create(
            request=request_obj,
            user=approver_user,
            order=i,
            status=SimpleApprover.STATUS_PENDING
        )


def validate_approvers(request, approvers_list):
    """
    承認者リストのバリデーションを行うヘルパー関数。
    """
    # 承認者が選択されているかチェック（最低1人）
    if not approvers_list:
        messages.error(request, "承認者を少なくとも1名指定してください。")
        return False

    # 自分自身が含まれていないかチェック
    if request.user in approvers_list:
        messages.error(request, "申請者本人を承認者に含めることはできません。")
        return False

    # 連続した重複チェック (A -> A は不可)
    for i in range(len(approvers_list) - 1):
        if approvers_list[i] == approvers_list[i+1]:
            messages.error(request, "同じ承認者を連続して設定することはできません。")
            return False

    return True


class RequestCreateView(LoginRequiredMixin, CreateView):
    """
    新規申請作成ビュー。
    """
    model = SimpleRequest
    form_class = RequestForm
    template_name = "approvals/request_form.html"
    success_url = reverse_lazy("portal:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["approver_formset"] = ApproverFormSet(self.request.POST)
        else:
            context["approver_formset"] = ApproverFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        approver_formset = context["approver_formset"]

        if not approver_formset.is_valid():
            return self.render_to_response(context)

        # 承認者リストの取得
        approvers = [
            f.cleaned_data.get("user")
            for f in approver_formset
            if f.cleaned_data.get("user")
        ]

        # 共通バリデーション
        if not validate_approvers(self.request, approvers):
            return self.render_to_response(context)

        try:
            with transaction.atomic():
                # 1. 採番ロックと申請番号生成
                now = timezone.now()
                yyyymm = now.strftime("%Y%m")
                prefix = f"REQ-S-{yyyymm}"

                # その月の最新の申請番号を取得してロック
                qs = SimpleRequest.objects.select_for_update()
                latest_request = qs.filter(
                    request_number__startswith=prefix
                ).order_by("-request_number").first()

                if latest_request:
                    last_num = int(
                        latest_request.request_number.split("-")[-1]
                    )
                    new_num = last_num + 1
                else:
                    new_num = 1

                request_number = f"{prefix}-{new_num:04d}"

                # 2. 申請保存
                self.object = form.save(commit=False)
                self.object.request_number = request_number
                self.object.applicant = self.request.user
                self.object.status = SimpleRequest.STATUS_PENDING
                self.object.submitted_at = now
                self.object.save()

                # 3. 承認者保存
                save_approvers(self.object, approvers)

                # 4. ログ記録
                SimpleApprovalLog.objects.create(
                    request=self.object,
                    actor=self.request.user,
                    action=SimpleApprovalLog.ACTION_SUBMIT,
                    step=None,
                    comment="新規申請"
                )

                # 5. メール通知（最初の承認者へ）
                first_approver = approvers[0]
                NotificationService.send_approval_request(
                    self.object, first_approver, self.request
                )

            messages.success(self.request, f"申請 {request_number} を提出しました。")
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error creating request: {e}", exc_info=True)
            messages.error(self.request, f"エラーが発生しました: {e}")
            return self.render_to_response(context)


class RequestUpdateView(LoginRequiredMixin, UpdateView):
    """
    再申請ビュー。
    """
    model = SimpleRequest
    form_class = RequestForm
    template_name = "approvals/request_form.html"
    success_url = reverse_lazy("portal:index")

    def get_queryset(self):
        # 申請者本人のもので、差戻し状態のものに限る
        return super().get_queryset().filter(
            applicant=self.request.user,
            status=SimpleRequest.STATUS_REMANDED
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["approver_formset"] = ApproverFormSet(
                self.request.POST, instance=self.object
            )
        else:
            context["approver_formset"] = ApproverFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        approver_formset = context["approver_formset"]

        if not approver_formset.is_valid():
            return self.render_to_response(context)

        # 承認者リストの取得
        # 再申請時はDELETEフラグは見ない（全洗い替えするため）
        approvers = [
            f.cleaned_data.get("user")
            for f in approver_formset
            if f.cleaned_data.get("user")
        ]

        # 共通バリデーション
        if not validate_approvers(self.request, approvers):
            return self.render_to_response(context)

        try:
            with transaction.atomic():
                # ロック取得
                self.object = SimpleRequest.objects.select_for_update().get(
                    pk=self.object.pk
                )

                # 申請情報の更新
                self.object = form.save(commit=False)
                self.object.status = SimpleRequest.STATUS_PENDING
                self.object.current_step = 1
                self.object.submitted_at = timezone.now()
                self.object.save()

                # 承認ルートの再構築 (全削除 -> 再作成)
                self.object.approvers.all().delete()
                save_approvers(self.object, approvers)

                # ログ記録
                SimpleApprovalLog.objects.create(
                    request=self.object,
                    actor=self.request.user,
                    action=SimpleApprovalLog.ACTION_RESUBMIT,
                    step=None,
                    comment="再申請"
                )

                # メール通知
                first_approver = self.object.approvers.filter(order=1).first()
                if first_approver:
                    NotificationService.send_resubmitted(
                        self.object, first_approver.user, self.request
                    )

            messages.success(
                self.request,
                f"申請 {self.object.request_number} を再提出しました。"
            )
            return redirect(self.success_url)

        except Exception as e:
            logger.error(f"Error updating request: {e}", exc_info=True)
            messages.error(self.request, f"エラーが発生しました: {e}")
            return self.render_to_response(context)


class RequestDetailView(DetailView):
    """
    申請詳細画面。
    """
    model = SimpleRequest
    template_name = "approvals/request_detail.html"
    context_object_name = "req"

    def get_queryset(self):
        # 関連データも一緒に取得（N+1問題対策）
        return super().get_queryset().select_related(
            "applicant"
        ).prefetch_related(
            "approvers__user",
            "logs__actor"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        req = self.object
        user = self.request.user

        # 現在のユーザーが承認すべき状態か判定
        can_approve = False
        current_approver = None

        is_pending = req.status == SimpleRequest.STATUS_PENDING
        if user.is_authenticated and is_pending:
            current_approver = req.approvers.filter(
                order=req.current_step,
                user=user,
                status=SimpleApprover.STATUS_PENDING
            ).first()
            if current_approver:
                can_approve = True

        context["can_approve"] = can_approve
        context["current_approver"] = current_approver
        context["action_form"] = ActionForm()

        # 申請者向けアクションフラグ
        if user.is_authenticated and req.applicant == user:
            context["can_withdraw"] = req.status in [
                SimpleRequest.STATUS_PENDING,
                SimpleRequest.STATUS_APPROVED
            ]
            context["can_resubmit"] = (
                req.status == SimpleRequest.STATUS_REMANDED
            )
        else:
            context["can_withdraw"] = False
            context["can_resubmit"] = False

        # 管理者向け代理差戻しフラグ
        if user.is_staff and req.status in [
            SimpleRequest.STATUS_PENDING, SimpleRequest.STATUS_APPROVED
        ]:
            context["can_proxy_remand"] = True
        else:
            context["can_proxy_remand"] = False

        # 閲覧制限チェック
        if req.is_restricted:
            has_permission = False
            if user.is_authenticated:
                related_users = {a.user.id for a in req.approvers.all()}
                related_users.add(req.applicant.id)
                if user.id in related_users or user.is_staff:
                    has_permission = True

            if not has_permission:
                context["permission_denied"] = True

        return context


class RequestActionView(LoginRequiredMixin, View):
    """
    承認アクション実行ビュー。
    """
    def post(self, request, pk):
        req = get_object_or_404(SimpleRequest, pk=pk)
        form = ActionForm(request.POST)

        if not form.is_valid():
            messages.error(request, "入力内容に誤りがあります。")
            return redirect("approvals:detail", pk=pk)

        comment = form.cleaned_data["comment"]
        action = request.POST.get("action")

        # アクションの種類判定
        if action not in ["approve", "remand", "reject"]:
            messages.error(request, "不正なアクションです。")
            return redirect("approvals:detail", pk=pk)

        # 権限チェックとロック取得のためにトランザクション開始
        try:
            with transaction.atomic():
                # ロック取得して再取得
                req = SimpleRequest.objects.select_for_update().get(pk=pk)

                # ステータスチェック
                if req.status != SimpleRequest.STATUS_PENDING:
                    messages.error(
                        request,
                        "この申請は既に処理されているか、"
                        "取り下げられています。"
                    )
                    return redirect("approvals:detail", pk=pk)

                # 承認者チェック
                approver = SimpleApprover.objects.select_for_update().filter(
                    request=req,
                    order=req.current_step,
                    user=request.user,
                    status=SimpleApprover.STATUS_PENDING
                ).first()

                if not approver:
                    messages.error(
                        request,
                        "あなたはこの申請の現在の承認者ではありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                now = timezone.now()
                approver.processed_at = now
                approver.comment = comment

                # アクション別処理
                if action == "approve":
                    approver.status = SimpleApprover.STATUS_APPROVED
                    approver.save()

                    # 次のステップへ
                    next_step = req.current_step + 1
                    next_approver = req.approvers.filter(
                        order=next_step
                    ).first()

                    if next_approver:
                        req.current_step = next_step
                        req.save()
                        # 次の承認者へメール
                        NotificationService.send_approval_request(
                            req, next_approver.user, request
                        )
                    else:
                        # 最終承認完了
                        req.status = SimpleRequest.STATUS_APPROVED
                        req.save()
                        # 申請者へメール
                        NotificationService.send_approved(req, request)

                    # ログ
                    self.log_action(
                        req, request.user, SimpleApprovalLog.ACTION_APPROVE,
                        req.current_step, comment
                    )
                    messages.success(request, "承認しました。")

                elif action == "remand":
                    if not comment:
                        raise ValueError("差戻しの場合はコメントが必須です。")

                    approver.status = SimpleApprover.STATUS_REMANDED
                    approver.save()

                    req.status = SimpleRequest.STATUS_REMANDED
                    req.save()

                    # 申請者へメール
                    NotificationService.send_remanded(
                        req, request.user, comment, request
                    )

                    # ログ
                    self.log_action(
                        req, request.user, SimpleApprovalLog.ACTION_REMAND,
                        req.current_step, comment
                    )
                    messages.warning(request, "差戻しました。")

                elif action == "reject":
                    if not comment:
                        raise ValueError("却下の場合はコメントが必須です。")

                    approver.status = SimpleApprover.STATUS_REJECTED
                    approver.save()

                    req.status = SimpleRequest.STATUS_REJECTED
                    req.save()

                    # 申請者へメール
                    NotificationService.send_rejected(
                        req, request.user, comment, request
                    )

                    # ログ
                    self.log_action(
                        req, request.user, SimpleApprovalLog.ACTION_REJECT,
                        req.current_step, comment
                    )
                    messages.error(request, "却下しました。")

        except ValueError as e:
            logger.warning(f"Validation error in RequestActionView: {e}")
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f"Error in RequestActionView: {e}", exc_info=True)
            messages.error(request, f"エラーが発生しました: {e}")

        return redirect("approvals:detail", pk=pk)

    def log_action(self, req, actor, action, step, comment):
        SimpleApprovalLog.objects.create(
            request=req,
            actor=actor,
            action=action,
            step=step,
            comment=comment
        )


class RequestWithdrawView(LoginRequiredMixin, View):
    """
    申請取り下げビュー。
    """
    def post(self, request, pk):
        req = get_object_or_404(SimpleRequest, pk=pk)

        # 権限チェック：申請者本人のみ
        if req.applicant != request.user:
            messages.error(request, "取り下げ権限がありません。")
            return redirect("approvals:detail", pk=pk)

        try:
            with transaction.atomic():
                req = SimpleRequest.objects.select_for_update().get(pk=pk)

                # ステータスチェック：Pending または Approved
                if req.status not in [
                        SimpleRequest.STATUS_PENDING,
                        SimpleRequest.STATUS_APPROVED
                ]:
                    messages.error(
                        request, "この申請は取り下げ可能な状態ではありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                req.status = SimpleRequest.STATUS_WITHDRAWN
                req.save()

                # ログ記録
                SimpleApprovalLog.objects.create(
                    request=req,
                    actor=request.user,
                    action=SimpleApprovalLog.ACTION_WITHDRAW,
                    step=None,
                    comment="申請者による取り下げ"
                )

                # メール通知（現在の承認者＆承認済み承認者）
                NotificationService.send_withdrawn(req, request)

            messages.info(request, "申請を取り下げました。")

        except Exception as e:
            logger.error(f"Error in RequestWithdrawView: {e}", exc_info=True)
            messages.error(request, f"エラーが発生しました: {e}")

        return redirect("approvals:detail", pk=pk)


class RequestProxyRemandView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    代理差戻しビュー（管理者用）。
    """
    def test_func(self):
        return self.request.user.is_staff

    def post(self, request, pk):
        req = get_object_or_404(SimpleRequest, pk=pk)
        form = ActionForm(request.POST)

        if not form.is_valid():
            messages.error(request, "入力内容に誤りがあります。")
            return redirect("approvals:detail", pk=pk)

        comment = form.cleaned_data["comment"]
        if not comment:
            messages.error(request, "代理差戻しにはコメントが必須です。")
            return redirect("approvals:detail", pk=pk)

        try:
            with transaction.atomic():
                req = SimpleRequest.objects.select_for_update().get(pk=pk)

                # ステータスチェック：Pending または Approved
                if req.status not in [
                        SimpleRequest.STATUS_PENDING,
                        SimpleRequest.STATUS_APPROVED
                ]:
                    messages.error(
                        request, "この申請は差戻し可能な状態ではありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                req.status = SimpleRequest.STATUS_REMANDED
                req.save()

                # 承認者のステータスを変更（現在の承認者を差戻し状態に）
                if req.current_step:
                    current = SimpleApprover.objects.filter(
                        request=req, order=req.current_step
                    ).first()
                    if current:
                        current.status = SimpleApprover.STATUS_REMANDED
                        current.processed_at = timezone.now()
                        current.save()

                # ログ記録
                SimpleApprovalLog.objects.create(
                    request=req,
                    actor=request.user,
                    action=SimpleApprovalLog.ACTION_PROXY_REMAND,
                    step=req.current_step,
                    comment=comment
                )

                # メール通知（申請者へ）
                NotificationService.send_proxy_remanded(
                    req, request.user, comment, request
                )

            messages.warning(request, "代理差戻しを実行しました。")

        except Exception as e:
            logger.error(
                f"Error in RequestProxyRemandView: {e}",
                exc_info=True
            )
            messages.error(request, f"エラーが発生しました: {e}")

        return redirect("approvals:detail", pk=pk)
