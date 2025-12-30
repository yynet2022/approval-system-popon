from dal import autocomplete
from django import forms
from django.db import models
from django.forms import inlineformset_factory, modelform_factory

from .models import Approver, Request


def create_request_form_class(model_class):
    """
    指定された申請モデルクラスに対応するModelFormクラスを動的に生成する。
    Bootstrap5用のクラスや、適切なウィジェットを自動適用する。
    """

    # 除外するフィールド（システム自動設定）
    exclude_fields = [
        "id",
        "request_number",
        "applicant",
        "status",
        "current_step",
        "submitted_at",
        "created_at",
        "updated_at",
    ]

    # デフォルトのウィジェット設定
    widgets = {
        "title": forms.TextInput(attrs={"class": "form-control"}),
        "is_restricted": forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        ),
    }

    # モデルのフィールドを走査してウィジェットを決定
    for field in model_class._meta.fields:
        if field.name in exclude_fields:
            continue

        # 既に定義済みの場合はスキップ
        if field.name in widgets:
            continue

        if isinstance(field, models.TextField):
            widgets[field.name] = forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            )
        elif isinstance(field, models.DateField):
            widgets[field.name] = forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            )
        elif isinstance(field, models.BooleanField):
            widgets[field.name] = forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            )
        elif field.choices:
            widgets[field.name] = forms.Select(
                attrs={"class": "form-select"}
            )
        else:
            # デフォルトはform-control適用
            widgets[field.name] = forms.TextInput(
                attrs={"class": "form-control"}
            )

    # フォームクラス生成
    return modelform_factory(
        model_class,
        exclude=exclude_fields,
        widgets=widgets
    )


class ApproverForm(forms.ModelForm):
    """
    承認者設定用フォーム（FormSetで使用）。
    """
    class Meta:
        model = Approver
        fields = ("user", "order")
        widgets = {
            "user": autocomplete.ModelSelect2(
                url="accounts:approver-autocomplete",
                attrs={
                    "data-placeholder": "承認者を検索...",
                    "class": "form-control"
                }
            ),
            "order": forms.HiddenInput(),  # 順序はJSで制御するため隠す
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ラベルを非表示にする（テーブルレイアウトにするため）
        self.fields["user"].label = ""
        # 必須チェックを外す（再申請時に空欄にすることで削除を可能にするため）
        self.fields["user"].required = False

    def has_changed(self) -> bool:
        """
        userが空の場合、orderに値が入っていても変更なしとみなす。
        JSでorderを自動入力してしまうため、この判定が必要。
        """
        if not super().has_changed():
            return False

        # order だけが変更されており、かつ user が入力されていない場合を検出
        changed = self.changed_data
        if len(changed) == 1 and "order" in changed:
            user_field_name = self.add_prefix("user")
            user_value = self.data.get(user_field_name)
            if not user_value:
                return False

        return True


# 承認者設定用フォームセット
ApproverFormSet = inlineformset_factory(
    Request,  # 汎用的にRequestを親とする
    Approver,
    form=ApproverForm,
    extra=2,      # 初期表示数
    max_num=5,    # 最大数
    can_delete=False
)


class ActionForm(forms.Form):
    """
    承認アクション用フォーム（コメント入力用）。
    """
    comment = forms.CharField(
        label="コメント",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,  # アクションによって必須かどうかが変わるため
        help_text="承認時は任意、それ以外（差戻・却下等）は必須です。"
    )
