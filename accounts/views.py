import logging
from dal import autocomplete
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.mail import send_mail
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.functions import Concat, Trim
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import LoginForm
from .models import LoginToken, User

logger = logging.getLogger(__name__)


def _annotate_display_name(queryset):
    """
    クエリセットに表示名（氏名、なければメール）のアノテーションを付与するヘルパー関数。
    ソートは行わない。
    """
    return queryset.annotate(
        full_name=Trim(Concat("last_name", Value(" "), "first_name")),
    ).annotate(
        display_name=Case(
            When(full_name="", then=F("email")),
            default=F("full_name"),
            output_field=CharField(),
        )
    )


class ApiLoginRequiredMixin(LoginRequiredMixin):
    """
    API用ログイン必須Mixin。
    未ログイン時にリダイレクトではなく403 Forbiddenを返す。
    """
    def handle_no_permission(self):
        return HttpResponseForbidden()


class ApproverAutocomplete(ApiLoginRequiredMixin,
                           autocomplete.Select2QuerySetView):
    """
    承認者検索用オートコンプリートビュー。
    検索語句がない場合: 承認者候補(is_approver=True)のみ表示
    検索語句がある場合: 全アクティブユーザーから検索し、承認者候補を優先表示
    """
    def get_queryset(self):
        # まずは全アクティブユーザーを対象にする（後で絞り込む）
        qs = User.objects.filter(is_active=True)

        # 自分自身は除外
        if self.request.user.is_authenticated:
            qs = qs.exclude(id=self.request.user.id)

        if self.q:
            # 検索時は全ユーザーから検索
            qs = qs.filter(
                Q(last_name__icontains=self.q) |
                Q(first_name__icontains=self.q) |
                Q(email__icontains=self.q)
            )
        else:
            # 検索語句がない場合は承認者候補のみ
            qs = qs.filter(is_approver=True)

        # 表示名アノテーション
        qs = _annotate_display_name(qs)

        # ソート: 承認者候補を優先(-is_approver) -> 表示名順
        return qs.order_by("-is_approver", "display_name")


class ActiveUserAutocomplete(ApiLoginRequiredMixin,
                             autocomplete.Select2QuerySetView):
    """
    全アクティブユーザー検索用オートコンプリートビュー。
    """
    def get_queryset(self):
        qs = User.objects.filter(is_active=True)

        if self.q:
            qs = qs.filter(
                Q(last_name__icontains=self.q) |
                Q(first_name__icontains=self.q) |
                Q(email__icontains=self.q)
            )

        # 表示名アノテーション
        qs = _annotate_display_name(qs)

        return qs.order_by("display_name")


class LoginView(View):
    """
    ログイン画面。メールアドレスを受け取り、マジックリンクを送信する。
    """
    def get(self, request):
        form = LoginForm()
        return render(request, "accounts/login.html", {"form": form})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            # ユーザーを自動作成または取得
            user, created = User.objects.get_or_create(email=email)

            # トークン発行
            token_record = LoginToken.create_token(user)

            # ログイン用URL作成
            verify_url = request.build_absolute_uri(
                reverse(
                    "accounts:verify",
                    kwargs={"token": token_record.token}
                )
            )

            # next パラメータがあれば付与
            next_path = request.GET.get("next") or request.POST.get("next")
            if next_path:
                verify_url += f"?next={next_path}"

            # メール送信
            try:
                subject = f"[{settings.PROJECT_NAME}] ログインURLのお知らせ"
                send_mail(
                    subject=subject,
                    message=(
                        f"{settings.PROJECT_NAME}をご利用いただくには、"
                        f"以下のURLからログインしてください。\n\n{verify_url}"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                return redirect("accounts:login_sent")
            except Exception as e:
                logger.error(
                    f"Failed to send login email to {email}: {e}",
                    exc_info=True
                )
                messages.error(request, f"メール送信に失敗しました: {e}")

        return render(request, "accounts/login.html", {"form": form})


class LoginSentView(View):
    """
    メール送信完了画面。
    """
    def get(self, request):
        return render(request, "accounts/login_sent.html")


class VerifyTokenView(View):
    """
    トークン検証ページ。
    """
    def get(self, request, token):
        token_record = LoginToken.objects.filter(token=token).first()

        # 無効判定
        if not token_record or token_record.expires_at < timezone.now():
            return render(
                request,
                "accounts/error.html",
                {"message": "無効なリンクか、有効期限切れです"},
                status=400
            )

        user = token_record.user
        # トークン削除（使い捨て）
        token_record.delete()

        # 初回ログイン時の有効化
        if not user.is_active:
            user.is_active = True
            user.save()

        # ログイン
        auth_login(request, user)

        # リダイレクト処理
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

        return redirect("portal:index")


class LogoutView(LoginRequiredMixin, View):
    """
    ログアウト処理。
    """
    def get(self, request):
        auth_logout(request)
        return redirect("portal:index")
