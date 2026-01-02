from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from dal import autocomplete

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
                "placeholder": "件名、申請番号で検索...",
            }
        ),
    )

    # mypy対策: 選択肢のキー(int)を文字列に変換して型を list[tuple[str, str]] に統一する
    _status_choices = [("", "全て")] + [
        (str(k), v) for k, v in Request.STATUS_CHOICES
    ]

    status = forms.ChoiceField(
        label="ステータス",
        required=False,
        choices=_status_choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    applicant = forms.ModelChoiceField(
        label="申請者",
        queryset=User.objects.filter(is_active=True),
        required=False,
        widget=autocomplete.ModelSelect2(
            url="accounts:active-user-autocomplete",
            attrs={
                "data-placeholder": "申請者を選択...",
                "class": "form-control",
            },
        ),
    )
    own_only = forms.BooleanField(
        label="自分の申請のみ",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
