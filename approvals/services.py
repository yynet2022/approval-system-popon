from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional, Union

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Approver

if TYPE_CHECKING:
    from django.http import HttpRequest

    from accounts.models import User
    from approvals.models import Request

logger = logging.getLogger(__name__)


class NotificationService:
    """
    承認フローに関するメール通知を行うサービス
    """

    @staticmethod
    def _send_email(
        to_user: Union[User, list[User], None],
        subject: str,
        template_name: str,
        context: dict[str, Any],
        cc_users: Optional[list[User]] = None,
    ) -> None:
        """
        内部用: メール送信実行メソッド
        Args:
            to_user: 送信先ユーザー (Userモデルインスタンス) またはそのリスト
            subject: 件名
            template_name: テンプレートファイル名
            context: テンプレート用コンテキスト
            cc_users: CC送付先ユーザーリスト (Userモデルインスタンスのリスト)
        """
        # 送信先リストの作成 (TO)
        to_emails: list[str] = []
        if isinstance(to_user, list):
            for u in to_user:
                if u.email:
                    to_emails.append(u.email)
        elif to_user and to_user.email:
            to_emails.append(to_user.email)

        # 送信先リストの作成 (CC)
        cc_emails: list[str] = []
        if cc_users:
            for u in cc_users:
                if u.email and u.email not in to_emails:
                    cc_emails.append(u.email)

        if not to_emails:
            logger.warning(
                f"No valid TO email addresses for subject: {subject}"
            )
            return

        message_body = render_to_string(template_name, context)

        try:
            email = EmailMessage(
                subject=subject,
                body=message_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to_emails,
                cc=cc_emails,
            )
            email.send(fail_silently=False)
        except Exception as e:
            logger.error(
                f"Failed to send email (Subject: {subject}): {e}",
                exc_info=True,
            )

    @classmethod
    def _get_detail_url(
        cls, request_obj: Request, request: Optional[HttpRequest] = None
    ) -> str:
        """
        申請詳細ページのURLを生成する
        """
        path = reverse("approvals:detail", kwargs={"pk": request_obj.pk})
        if request:
            return request.build_absolute_uri(path)

        # requestがない場合のフォールバック（簡易的）
        return f"http://localhost:8000{path}"

    @classmethod
    def send_approval_request(
        cls,
        request_obj: Request,
        next_approver: User,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        承認依頼
        To: 次の承認者 (next_approver)
        """
        subject = f"[{settings.PROJECT_NAME}] 承認依頼: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "link": cls._get_detail_url(request_obj, request),
        }
        cls._send_email(
            next_approver, subject, "emails/approval_request.txt", context
        )

    @classmethod
    def send_resubmitted(
        cls,
        request_obj: Request,
        first_approver: User,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        再申請通知
        To: 最初の承認者
        """
        subject = f"[{settings.PROJECT_NAME}] 再承認依頼: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "link": cls._get_detail_url(request_obj, request),
        }
        cls._send_email(
            first_approver, subject, "emails/resubmitted.txt", context
        )

    @classmethod
    def send_approved(
        cls, request_obj: Request, request: Optional[HttpRequest] = None
    ) -> None:
        """
        承認完了通知
        To: 申請者
        Cc: 全承認者
        """
        cc_users = [approver.user for approver in request_obj.approvers.all()]

        subject = f"[{settings.PROJECT_NAME}] 承認完了: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "link": cls._get_detail_url(request_obj, request),
        }

        cls._send_email(
            request_obj.applicant,
            subject,
            "emails/approved.txt",
            context,
            cc_users=cc_users,
        )

    @classmethod
    def send_remanded(
        cls,
        request_obj: Request,
        actor: User,
        comment: str,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        差戻し通知
        To: 申請者
        Cc: 本承認者(実行者) + 承認済の過去の承認者
        """
        cc_users_set = {actor}  # 実行者 (setで重複排除)

        # 承認済みの承認者
        approved_approvers = request_obj.approvers.filter(
            status=Approver.STATUS_APPROVED
        )
        for approver in approved_approvers:
            cc_users_set.add(approver.user)

        subject = f"[{settings.PROJECT_NAME}] 差戻し: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "actor": actor,
            "comment": comment,
            "link": cls._get_detail_url(request_obj, request),
        }

        cls._send_email(
            request_obj.applicant,
            subject,
            "emails/remanded.txt",
            context,
            cc_users=list(cc_users_set),
        )

    @classmethod
    def send_rejected(
        cls,
        request_obj: Request,
        actor: User,
        comment: str,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        却下通知
        To: 申請者
        Cc: 実行者 + 承認済みの承認者
        """
        cc_users_set = {actor}  # 実行者 (setで重複排除)

        # 承認済みの承認者
        approved_approvers = request_obj.approvers.filter(
            status=Approver.STATUS_APPROVED
        )
        for approver in approved_approvers:
            cc_users_set.add(approver.user)

        subject = f"[{settings.PROJECT_NAME}] 却下: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "actor": actor,
            "comment": comment,
            "link": cls._get_detail_url(request_obj, request),
        }

        cls._send_email(
            request_obj.applicant,
            subject,
            "emails/rejected.txt",
            context,
            cc_users=list(cc_users_set),
        )

    @classmethod
    def send_withdrawn(
        cls, request_obj: Request, request: Optional[HttpRequest] = None
    ) -> None:
        """
        取り下げ通知
        To: 現在の承認者(Pending)
        Cc: 承認済みの承認者
        """
        # To: 現在の承認者
        current_approver_obj = request_obj.approvers.filter(
            status=Approver.STATUS_PENDING, order=request_obj.current_step
        ).first()

        to_user = current_approver_obj.user if current_approver_obj else None

        # Cc: 承認済みの承認者
        approved_approvers = request_obj.approvers.filter(
            status=Approver.STATUS_APPROVED
        )
        cc_users = [approver.user for approver in approved_approvers]

        subject = f"[{settings.PROJECT_NAME}] 取り下げ: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "link": cls._get_detail_url(request_obj, request),
        }

        if to_user:
            cls._send_email(
                to_user,
                subject,
                "emails/withdrawn.txt",
                context,
                cc_users=cc_users,
            )
        else:
            # 万が一現在の承認者がいない場合(イレギュラー)はCcの人にToで送るなどの救済が必要だが
            # ここではCcの人だけに送る形にする（to_userリスト対応済みロジックにて）
            if cc_users:
                cls._send_email(
                    cc_users,  # リストを渡して全員TOにする
                    subject,
                    "emails/withdrawn.txt",
                    context,
                )

    @classmethod
    def send_proxy_remanded(
        cls,
        request_obj: Request,
        actor: User,
        comment: str,
        request: Optional[HttpRequest] = None,
    ) -> None:
        """
        代理差戻し通知
        To: 申請者
        Cc: 承認済みの人 + 現在の担当者
        """
        # 承認済みの承認者
        approved = request_obj.approvers.filter(
            status=Approver.STATUS_APPROVED
        )
        # 現在の承認者（Pending かつ 現在のステップ）
        #   呼び出し元で Remanded にしている
        current = request_obj.approvers.filter(
            # status=Approver.STATUS_PENDING,
            order=request_obj.current_step
        )

        related = approved | current
        cc_users = list(set(approver.user for approver in related))

        subject = f"[{settings.PROJECT_NAME}] 代理差戻し: {request_obj.title}"
        context = {
            "request_obj": request_obj,
            "actor": actor,
            "comment": comment,
            "link": cls._get_detail_url(request_obj, request),
        }

        cls._send_email(
            request_obj.applicant,
            subject,
            "emails/proxy_remanded.txt",
            context,
            cc_users=cc_users,
        )
