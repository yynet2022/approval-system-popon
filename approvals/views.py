import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, UpdateView

from .forms import (
    ActionForm,
    ApproverFormSet,
    LocalBusinessTripRequestForm,
    SimpleRequestForm,
)
from .models import (
    ApprovalLog,
    Approver,
    LocalBusinessTripRequest,
    Request,
    SimpleRequest,
)
from .services import NotificationService

logger = logging.getLogger(__name__)


def save_approvers(request_obj, approvers_list):
    """
    承認者リストを保存するヘルパー関数。
    """
    for i, approver_user in enumerate(approvers_list, start=1):
        Approver.objects.create(
            request=request_obj,
            user=approver_user,
            order=i,
            status=Approver.STATUS_PENDING
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


class BaseRequestCreateView(LoginRequiredMixin, CreateView):
    """
    申請作成の基底ビュー。
    共通の保存ロジック（承認者設定、ログ記録、メール送信）を持つ。
    """
    template_name = "approvals/request_form.html"
    success_url = reverse_lazy("portal:index")
    request_prefix = "REQ"  # サブクラスでオーバーライドする

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["approver_formset"] = ApproverFormSet(self.request.POST)
        else:
            context["approver_formset"] = ApproverFormSet()
        return context

    def generate_request_number(self):
        """
        申請番号を生成する。
        形式: {PREFIX}-{YYYYMM}-{NNNN}
        """
        now = timezone.now()
        yyyymm = now.strftime("%Y%m")
        prefix = f"{self.request_prefix}-{yyyymm}"

        # その月の最新の申請番号を取得してロック
        # NOTE: Request全体で連番を共有するか、Prefixごとに分けるか。
        # ここではPrefixごとに連番を振るロジックにする。
        qs = Request.objects.select_for_update()
        latest_request = qs.filter(
            request_number__startswith=prefix
        ).order_by("-request_number").first()

        if latest_request:
            last_num = int(latest_request.request_number.split("-")[-1])
            new_num = last_num + 1
        else:
            new_num = 1

        return f"{prefix}-{new_num:04d}"

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
                # 1. 申請番号生成
                request_number = self.generate_request_number()

                # 2. 申請保存
                self.object = form.save(commit=False)
                self.object.request_number = request_number
                self.object.applicant = self.request.user
                self.object.status = Request.STATUS_PENDING
                self.object.submitted_at = timezone.now()
                self.object.save()

                # 3. 承認者保存
                save_approvers(self.object, approvers)

                # 4. ログ記録
                ApprovalLog.objects.create(
                    request=self.object,
                    actor=self.request.user,
                    action=ApprovalLog.ACTION_SUBMIT,
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


class SimpleRequestCreateView(BaseRequestCreateView):
    """簡易申請作成ビュー"""
    model = SimpleRequest
    form_class = SimpleRequestForm
    request_prefix = "REQ-S"


class LocalBusinessTripRequestCreateView(BaseRequestCreateView):
    """近距離出張申請作成ビュー"""
    model = LocalBusinessTripRequest
    form_class = LocalBusinessTripRequestForm
    request_prefix = "REQ-L"


class RequestUpdateView(LoginRequiredMixin, UpdateView):
    """
    再申請ビュー。
    申請タイプに応じてフォームを切り替える。
    """
    model = Request
    template_name = "approvals/request_form.html"
    success_url = reverse_lazy("portal:index")

    def get_object(self, queryset=None):
        """
        Requestオブジェクトを取得し、具体的な子モデルのインスタンスに変換して返す。
        """
        obj = super().get_object(queryset)
        
        # 子モデルへのダウンキャスト
        if hasattr(obj, 'simplerequest'):
            return obj.simplerequest
        elif hasattr(obj, 'localbusinesstriprequest'):
            return obj.localbusinesstriprequest
        return obj

    def get_form_class(self):
        """
        オブジェクトの型に応じてフォームクラスを返す。
        """
        obj = self.object
        if isinstance(obj, SimpleRequest):
            return SimpleRequestForm
        elif isinstance(obj, LocalBusinessTripRequest):
            return LocalBusinessTripRequestForm
        return SimpleRequestForm  # フォールバック

    def get_queryset(self):
        # 申請者本人のもので、差戻し状態のものに限る
        return super().get_queryset().filter(
            applicant=self.request.user,
            status=Request.STATUS_REMANDED
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
                # ロック取得 (親モデルでロック)
                # self.object は get_object で子モデルになっているので、pkを使って再取得
                self.object = Request.objects.select_for_update().get(
                    pk=self.object.pk
                )

                # 申請情報の更新 (form.saveを使うために、formのinstanceを更新)
                # form.save() は子モデルのフィールドも保存してくれる
                updated_object = form.save(commit=False)
                updated_object.status = Request.STATUS_PENDING
                updated_object.current_step = 1
                updated_object.submitted_at = timezone.now()
                updated_object.save()
                
                # self.object を更新後のものに置き換え
                self.object = updated_object

                # 承認ルートの再構築 (全削除 -> 再作成)
                self.object.approvers.all().delete()
                save_approvers(self.object, approvers)

                # ログ記録
                ApprovalLog.objects.create(
                    request=self.object,
                    actor=self.request.user,
                    action=ApprovalLog.ACTION_RESUBMIT,
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
    model = Request
    template_name = "approvals/request_detail.html"
    context_object_name = "req"

    def get_queryset(self):
        return super().get_queryset().select_related(
            "applicant"
        ).prefetch_related(
            "approvers__user",
            "logs__actor"
        )
    
    def get_object(self, queryset=None):
        """
        表示用に子モデルのインスタンスを取得して返す。
        これによりテンプレートで req.content や req.trip_date にアクセスできる。
        """
        obj = super().get_object(queryset)
        if hasattr(obj, 'simplerequest'):
            return obj.simplerequest
        elif hasattr(obj, 'localbusinesstriprequest'):
            return obj.localbusinesstriprequest
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        req = self.object
        user = self.request.user

        # 現在のユーザーが承認すべき状態か判定
        can_approve = False
        current_approver = None

        is_pending = req.status == Request.STATUS_PENDING
        if user.is_authenticated and is_pending:
            current_approver = req.approvers.filter(
                order=req.current_step,
                user=user,
                status=Approver.STATUS_PENDING
            ).first()
            if current_approver:
                can_approve = True

        context["can_approve"] = can_approve
        context["current_approver"] = current_approver
        context["action_form"] = ActionForm()

        # 事後却下可能フラグ
        can_reject_after_approval = False
        if user.is_authenticated and req.status == Request.STATUS_APPROVED:
            if req.approvers.filter(user=user).exists():
                can_reject_after_approval = True
        context["can_reject_after_approval"] = can_reject_after_approval

        # 申請者向けアクションフラグ
        if user.is_authenticated and req.applicant == user:
            context["can_withdraw"] = req.status in [
                Request.STATUS_PENDING,
                Request.STATUS_APPROVED,
                Request.STATUS_REMANDED
            ]
            context["can_resubmit"] = (
                req.status == Request.STATUS_REMANDED
            )
        else:
            context["can_withdraw"] = False
            context["can_resubmit"] = False

        # 管理者向け代理差戻しフラグ
        if user.is_staff and req.status in [
            Request.STATUS_PENDING, Request.STATUS_APPROVED
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
        req = get_object_or_404(Request, pk=pk)
        form = ActionForm(request.POST)

        if not form.is_valid():
            messages.error(request, "入力内容に誤りがあります。")
            return redirect("approvals:detail", pk=pk)

        comment = form.cleaned_data["comment"]
        action = request.POST.get("action")

        if action not in ["approve", "remand", "reject"]:
            messages.error(request, "不正なアクションです。")
            return redirect("approvals:detail", pk=pk)

        try:
            with transaction.atomic():
                req = Request.objects.select_for_update().get(pk=pk)
                approver = None

                if action == "reject":
                    if req.status not in [Request.STATUS_PENDING,
                                          Request.STATUS_APPROVED]:
                        messages.error(
                            request,
                            "この申請は却下可能な状態ではありません。"
                        )
                        return redirect("approvals:detail", pk=pk)

                    if req.status == Request.STATUS_APPROVED:
                        approver = Approver.objects \
                                           .select_for_update() \
                                           .filter(
                                               request=req,
                                               user=request.user
                                           ).first()
                    else:
                        approver = Approver.objects \
                            .select_for_update().filter(
                                request=req,
                                order=req.current_step,
                                user=request.user,
                                status=Approver.STATUS_PENDING
                            ).first()

                else:
                    if req.status != Request.STATUS_PENDING:
                        messages.error(
                            request,
                            "この申請は既に処理されているか、取り下げられています。"
                        )
                        return redirect("approvals:detail", pk=pk)

                    approver = Approver.objects \
                        .select_for_update().filter(
                            request=req,
                            order=req.current_step,
                            user=request.user,
                            status=Approver.STATUS_PENDING
                        ).first()

                if not approver:
                    messages.error(
                        request,
                        "あなたはこの申請に対して操作を行う権限がありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                now = timezone.now()
                approver.processed_at = now
                approver.comment = comment

                if action == "approve":
                    approver.status = Approver.STATUS_APPROVED
                    approver.save()

                    next_step = req.current_step + 1
                    next_approver = req.approvers.filter(
                        order=next_step
                    ).first()

                    if next_approver:
                        req.current_step = next_step
                        req.save()
                        NotificationService.send_approval_request(
                            req, next_approver.user, request
                        )
                    else:
                        req.status = Request.STATUS_APPROVED
                        req.save()
                        NotificationService.send_approved(req, request)

                    self.log_action(
                        req, request.user, ApprovalLog.ACTION_APPROVE,
                        req.current_step, comment
                    )
                    messages.success(request, "承認しました。")

                elif action == "remand":
                    if not comment:
                        raise ValueError("差戻しの場合はコメントが必須です。")

                    approver.status = Approver.STATUS_REMANDED
                    approver.save()

                    req.status = Request.STATUS_REMANDED
                    req.save()

                    NotificationService.send_remanded(
                        req, request.user, comment, request
                    )

                    self.log_action(
                        req, request.user, ApprovalLog.ACTION_REMAND,
                        req.current_step, comment
                    )
                    messages.warning(request, "差戻しました。")

                elif action == "reject":
                    if not comment:
                        raise ValueError("却下の場合はコメントが必須です。")

                    approver.status = Approver.STATUS_REJECTED
                    approver.save()

                    req.status = Request.STATUS_REJECTED
                    req.save()

                    NotificationService.send_rejected(
                        req, request.user, comment, request
                    )

                    self.log_action(
                        req, request.user, ApprovalLog.ACTION_REJECT,
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
        ApprovalLog.objects.create(
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
        req = get_object_or_404(Request, pk=pk)

        if req.applicant != request.user:
            messages.error(request, "取り下げ権限がありません。")
            return redirect("approvals:detail", pk=pk)

        try:
            with transaction.atomic():
                req = Request.objects.select_for_update().get(pk=pk)

                if req.status not in [
                        Request.STATUS_PENDING,
                        Request.STATUS_APPROVED,
                        Request.STATUS_REMANDED
                ]:
                    messages.error(
                        request, "この申請は取り下げ可能な状態ではありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                is_remanded_withdraw = (
                    req.status == Request.STATUS_REMANDED)

                req.status = Request.STATUS_WITHDRAWN
                req.save()

                if not is_remanded_withdraw:
                    NotificationService.send_withdrawn(req, request)

                ApprovalLog.objects.create(
                    request=req,
                    actor=request.user,
                    action=ApprovalLog.ACTION_WITHDRAW,
                    step=None,
                    comment="申請者による取り下げ"
                )

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
        req = get_object_or_404(Request, pk=pk)
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
                req = Request.objects.select_for_update().get(pk=pk)

                if req.status not in [
                        Request.STATUS_PENDING,
                        Request.STATUS_APPROVED
                ]:
                    messages.error(
                        request, "この申請は差戻し可能な状態ではありません。"
                    )
                    return redirect("approvals:detail", pk=pk)

                req.status = Request.STATUS_REMANDED
                req.save()

                if req.current_step:
                    current = Approver.objects.filter(
                        request=req, order=req.current_step
                    ).first()
                    if current:
                        current.status = Approver.STATUS_REMANDED
                        current.processed_at = timezone.now()
                        current.save()

                ApprovalLog.objects.create(
                    request=req,
                    actor=request.user,
                    action=ApprovalLog.ACTION_PROXY_REMAND,
                    step=req.current_step,
                    comment=comment
                )

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
