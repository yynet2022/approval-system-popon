from django import forms


class LoginForm(forms.Form):
    """
    マジックリンク送信用のメールアドレス入力フォーム。
    """

    email = forms.EmailField(
        label="メールアドレス",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "example@example.com",
                "required": True,
            }
        ),
    )
