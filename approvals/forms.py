from django import forms
from django.db import models
from django.forms import inlineformset_factory, modelform_factory

from dal import autocomplete

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

    # モデル側での指定を優先しつつ、デフォルトのウィジェット設定をマージ
    widgets = model_class.get_widgets()

    if "title" not in widgets:
        widgets["title"] = forms.TextInput(attrs={"class": "form-control"})
    if "is_restricted" not in widgets:
        widgets["is_restricted"] = forms.CheckboxInput(
            attrs={"class": "form-check-input"}
        )

    # モデルのフィールドを走査してウィジェットを決定 (通常フィールド)
    for field in model_class._meta.fields:
        if field.name in exclude_fields:
            continue

        # 既に定義済みの場合はスキップ
        if field.name in widgets:
            continue

        # 1. 選択肢があるフィールド、または外部キー -> Select
        if field.choices or isinstance(field, models.ForeignKey):
            widgets[field.name] = forms.Select(attrs={"class": "form-select"})
        # 2. ブール値 -> Checkbox
        elif isinstance(field, models.BooleanField):
            widgets[field.name] = forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            )
        # 3. テキストエリア
        elif isinstance(field, models.TextField):
            widgets[field.name] = forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            )
        # 4. 日付
        elif isinstance(field, models.DateField):
            widgets[field.name] = forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            )
        # 5. 日時
        elif isinstance(field, models.DateTimeField):
            widgets[field.name] = forms.DateTimeInput(
                attrs={"class": "form-control", "type": "datetime-local"}
            )
        # 6. 数値
        elif isinstance(
            field,
            (models.IntegerField, models.DecimalField, models.FloatField),
        ):
            widgets[field.name] = forms.NumberInput(
                attrs={"class": "form-control"}
            )
        # 7. メールアドレス
        elif isinstance(field, models.EmailField):
            widgets[field.name] = forms.EmailInput(
                attrs={"class": "form-control"}
            )
        # 8. URL
        elif isinstance(field, models.URLField):
            widgets[field.name] = forms.URLInput(
                attrs={"class": "form-control"}
            )
        # 9. その他デフォルト -> TextInput
        else:
            widgets[field.name] = forms.TextInput(
                attrs={"class": "form-control"}
            )

    # ManyToManyField の判定を追加
    for field in model_class._meta.many_to_many:
        if field.name in exclude_fields or field.name in widgets:
            continue
        widgets[field.name] = forms.SelectMultiple(
            attrs={"class": "form-select"}
        )

    # フォームクラス生成
    return modelform_factory(
        model_class,
        exclude=exclude_fields,
        widgets=widgets,
        labels=model_class.get_labels(),
        help_texts=model_class.get_help_texts(),
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
                    "class": "form-control",
                },
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
    extra=2,  # 初期表示数
    max_num=5,  # 最大数
    can_delete=False,
)


class ActionForm(forms.Form):
    """
    承認アクション用フォーム（コメント入力用）。
    """

    comment = forms.CharField(
        label="コメント",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,  # アクションによって必須かどうかが変わるため
        help_text="承認時は任意、それ以外（差戻・却下等）は必須です。",
    )
