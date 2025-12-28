from django.conf import settings
from django.db import models

from core.models import BaseModel


class SimpleRequest(BaseModel):
    """
    簡易承認申請モデル。
    """
    STATUS_DRAFT = 0
    STATUS_PENDING = 1
    STATUS_APPROVED = 2
    STATUS_REMANDED = 3
    STATUS_WITHDRAWN = 4
    STATUS_REJECTED = 9

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft (下書き)"),
        (STATUS_PENDING, "Pending (申請中)"),
        (STATUS_APPROVED, "Approved (承認完了)"),
        (STATUS_REMANDED, "Remanded (差戻)"),
        (STATUS_WITHDRAWN, "Withdrawn (取り下げ)"),
        (STATUS_REJECTED, "Rejected (却下)"),
    ]

    request_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="申請番号"
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="申請者"
    )
    title = models.CharField(
        max_length=100,
        verbose_name="件名"
    )
    content = models.TextField(
        verbose_name="内容"
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        verbose_name="ステータス"
    )
    current_step = models.IntegerField(
        default=1,
        verbose_name="現在のステップ"
    )
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="申請日時"
    )
    is_restricted = models.BooleanField(
        default=False,
        verbose_name="閲覧制限フラグ"
    )

    def __str__(self):
        return f"{self.request_number}: {self.title}"


class SimpleApprover(BaseModel):
    """
    承認者設定モデル。
    """
    STATUS_PENDING = 0
    STATUS_APPROVED = 1
    STATUS_REMANDED = 2
    STATUS_REJECTED = 9

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending (未処理)"),
        (STATUS_APPROVED, "Approved (承認)"),
        (STATUS_REMANDED, "Remanded (差戻)"),
        (STATUS_REJECTED, "Rejected (却下)"),
    ]

    request = models.ForeignKey(
        SimpleRequest,
        on_delete=models.CASCADE,
        related_name="approvers"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="承認者"
    )
    order = models.IntegerField(
        verbose_name="順序"
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name="判定状態"
    )
    comment = models.TextField(
        blank=True,
        verbose_name="承認者コメント"
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="処理日時"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        display_name = self.user.get_display_name()
        return f"{self.request.request_number} - {self.order}: {display_name}"


class SimpleApprovalLog(BaseModel):
    """
    承認履歴ログモデル。
    """
    ACTION_SUBMIT = 1
    ACTION_APPROVE = 2
    ACTION_REMAND = 3
    ACTION_RESUBMIT = 4
    ACTION_WITHDRAW = 5
    ACTION_REJECT = 9
    ACTION_PROXY_REMAND = 10

    ACTION_CHOICES = [
        (ACTION_SUBMIT, "Submit (申請)"),
        (ACTION_APPROVE, "Approve (承認)"),
        (ACTION_REMAND, "Remand (差戻)"),
        (ACTION_RESUBMIT, "Resubmit (再申請)"),
        (ACTION_WITHDRAW, "Withdraw (取り下げ)"),
        (ACTION_REJECT, "Reject (却下)"),
        (ACTION_PROXY_REMAND, "ProxyRemand (代理差戻)"),
    ]

    request = models.ForeignKey(
        SimpleRequest,
        on_delete=models.CASCADE,
        related_name="logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="実行者"
    )
    action = models.IntegerField(
        choices=ACTION_CHOICES,
        verbose_name="アクション"
    )
    step = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="実行時のステップ"
    )
    comment = models.TextField(
        blank=True,
        null=True,
        verbose_name="コメント"
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.request.request_number} - {self.get_action_display()}"
