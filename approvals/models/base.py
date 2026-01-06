from __future__ import annotations

from typing import Any, Iterator, Optional

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models import OneToOneRel

from core.models import BaseModel


class Request(BaseModel):
    """
    申請の基底モデル（マルチテーブル継承の親）。
    全ての申請タイプに共通するフィールドとロジックを定義する。
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
        max_length=20, unique=True, verbose_name="申請番号"
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="申請者",
    )
    title = models.CharField(max_length=100, verbose_name="件名")
    status = models.IntegerField(
        choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name="ステータス"
    )
    current_step = models.IntegerField(
        default=1, verbose_name="現在のステップ"
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="申請日時"
    )
    is_restricted = models.BooleanField(
        default=False, verbose_name="閲覧制限フラグ"
    )

    # クラスごとの設定（サブクラスでオーバーライド）
    request_prefix: str = "REQ"
    url_slug: Optional[str] = (
        None  # URLで使用する識別子（例: 'simple'）。未設定の場合はクラス名小文字になる
    )

    @classmethod
    def get_request_types(cls) -> list[type[Request]]:
        """
        利用可能な申請タイプ（Requestの具象サブクラス）のリストを返す。
        """

        def get_all_subs(p: type[Request]) -> Iterator[type[Request]]:
            for sub in p.__subclasses__():
                # 孫クラスを再帰的に取得
                yield from get_all_subs(sub)
                # 自身が抽象クラスでなければ返す
                if not sub._meta.abstract:
                    yield sub

        # setで重複を除去しつつリスト化（多重継承対策）
        return list(set(get_all_subs(cls)))
        # subclasses = cls.__subclasses__()
        # return [c for c in subclasses if not c._meta.abstract]

    @classmethod
    def get_by_slug(cls, slug: str) -> Optional[type[Request]]:
        """
        スラッグから対応するモデルクラスを返す。
        """
        for subclass in cls.get_request_types():
            if subclass.get_slug() == slug:
                return subclass
        return None

    @classmethod
    def get_slug(cls) -> str:
        """
        このモデルのURLスラッグを返す。
        """
        if cls.url_slug:
            return cls.url_slug
        # デフォルト:
        # モデル名から 'request' を除いた小文字 (SimpleRequest -> simple)
        name = cls.__name__.lower()
        if name.endswith("request") and name != "request":
            return name[:-7]
        return name

    @classmethod
    def get_help_texts(cls) -> dict[str, str]:
        """
        フォーム生成時に使用するhelp_textの辞書を返す。
        サブクラスでオーバーライドして使用する。
        例: return {"title": "具体的な件名を入力してください"}
        """
        return {}

    @classmethod
    def get_labels(cls) -> dict[str, str]:
        """
        フォーム生成時に使用するlabelsの辞書を返す。
        """
        return {}

    @classmethod
    def get_widgets(cls) -> dict[str, Any]:
        """
        フォーム生成時に使用するwidgetsの辞書を返す。
        """
        return {}

    def get_real_instance(self) -> Request:
        """
        自身に関連付けられた子モデルのインスタンスを返す。
        子モデルが見つからない場合は自分自身(Request)を返す。
        """
        # 関連オブジェクト（逆参照）の中から、マルチテーブル継承のリンクを探す
        for field in self._meta.get_fields():
            if isinstance(field, OneToOneRel) and field.parent_link:
                # 型チェック: related_model が文字列や 'self' でないことを確認
                if not isinstance(field.related_model, type) or not issubclass(
                    field.related_model, models.Model
                ):
                    continue

                try:
                    # 子モデルへのアクセサ
                    # （例: simplerequest）を使って取得を試みる
                    accessor_name = field.get_accessor_name()
                    if accessor_name:
                        return getattr(self, accessor_name)
                except ObjectDoesNotExist:
                    continue
        return self

    def get_extra_fields(self) -> list[dict[str, Any]]:
        """
        詳細表示用に、Requestモデル固有のフィールドを除いた
        フィールド情報のリストを返す。
        （デフォルトテンプレートで使用）
        """
        data: list[dict[str, Any]] = []
        # 親モデル(Request)のフィールド名セット
        # 注意: selfがRequestインスタンスの場合もあるが、
        #       通常はサブクラスのインスタンスで呼ばれる
        parent_field_names = {f.name for f in Request._meta.fields}

        for field in self._meta.fields:
            # 親モデルにあるフィールドはスキップ
            # （件名などは共通表示エリアに出るため）
            if field.name in parent_field_names:
                continue

            # IDや内部的なフィールドもスキップ
            if field.name == "id":
                continue

            value = getattr(self, field.name)

            # 表示用の値を調整
            if hasattr(self, f"get_{field.name}_display"):
                value = getattr(self, f"get_{field.name}_display")()

            data.append({"label": field.verbose_name, "value": value})
        return data

    @property
    def detail_template_name(self) -> str:
        """
        詳細表示用のテンプレートパスを返す。
        デフォルトは 'approvals/partials/detail_{model_name}.html'。
        """
        return f"approvals/partials/detail_{self._meta.model_name}.html"

    @property
    def form_class_name(self) -> str:
        """
        対応するフォームクラス名を返す。
        デフォルトは '{ModelName}Form'。
        """
        return f"{self._meta.object_name}Form"

    @property
    def model_verbose_name(self) -> str:
        return str(self._meta.verbose_name)

    def __str__(self) -> str:
        return f"{self.request_number}: {self.title}"


class Approver(BaseModel):
    """
    承認者設定モデル。
    Requestモデルに紐づく。
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
        Request, on_delete=models.CASCADE, related_name="approvers"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="承認者",
    )
    order = models.IntegerField(verbose_name="順序")
    status = models.IntegerField(
        choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="判定状態"
    )
    comment = models.TextField(blank=True, verbose_name="承認者コメント")
    processed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="処理日時"
    )

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        # Userモデルのメソッドを使うが、ここは遅延インポート等は不要
        # DjangoのForeignKeyは自動的に関連モデルのインスタンスを返すため
        display_name = self.user.get_display_name()
        return f"{self.request.request_number} - {self.order}: {display_name}"


class ApprovalLog(BaseModel):
    """
    承認履歴ログモデル。
    Requestモデルに紐づく。
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
        Request, on_delete=models.CASCADE, related_name="logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="実行者",
    )
    action = models.IntegerField(
        choices=ACTION_CHOICES, verbose_name="アクション"
    )
    step = models.IntegerField(
        null=True, blank=True, verbose_name="実行時のステップ"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="コメント")

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.request.request_number} - {self.get_action_display()}"
