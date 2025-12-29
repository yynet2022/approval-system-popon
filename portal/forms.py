from dal import autocomplete
from django import forms
from django.contrib.auth import get_user_model

from approvals.models import Request

User = get_user_model()


class SearchForm(forms.Form):
    """
    ポータル検索用フォーム。
    """
    q = forms.CharField(
        label="キーワード",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "件名、申請番号で検索..."
            }
        )
    )
    status = forms.ChoiceField(
        label="ステータス",
        required=False,
        choices=[("", "全て")] + Request.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"})
    )
    applicant = forms.ModelChoiceField(
        label="申請者",
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="accounts:active-user-autocomplete",
            attrs={
                "data-placeholder": "申請者を選択...",
                "class": "form-control"
            }
        )
    )
    own_only = forms.BooleanField(
        label="自分の申請のみ",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )
