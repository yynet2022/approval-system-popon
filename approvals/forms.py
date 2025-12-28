from dal import autocomplete
from django import forms
from django.forms import inlineformset_factory

from .models import Approver, LocalBusinessTripRequest, SimpleRequest


class SimpleRequestForm(forms.ModelForm):
    """
    新規申請作成用フォーム（簡易申請用）。
    """
    class Meta:
        model = SimpleRequest
        fields = ("title", "content", "is_restricted")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(
                attrs={"class": "form-control", "rows": 5}
            ),
            "is_restricted": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class LocalBusinessTripRequestForm(forms.ModelForm):
    """
    新規申請作成用フォーム（近距離出張申請用）。
    """
    class Meta:
        model = LocalBusinessTripRequest
        fields = ("title", "trip_date", "destination", "note", "is_restricted")
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "trip_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "destination": forms.TextInput(attrs={"class": "form-control"}),
            "note": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "is_restricted": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


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
# NOTE: 親モデルがSimpleRequestだが、ApproverはRequestに紐づく。
# Djangoのinlineformset_factoryは、親モデルのインスタンスをfkとしてセットしようとする。
# SimpleRequestはRequestを継承しているので、Approver.request (Request型) に代入可能。
ApproverFormSet = inlineformset_factory(
    SimpleRequest,
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
