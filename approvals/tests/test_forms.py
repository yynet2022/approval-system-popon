from django.test import SimpleTestCase

from approvals.forms import create_request_form_class

# from approvals.models import Request
from approvals.models.types import SimpleRequest


class RequestFormTest(SimpleTestCase):
    """
    申請フォーム生成ロジックのテスト
    DBアクセスを伴わないためSimpleTestCaseを使用
    """

    def test_custom_help_text_in_form(self):
        """モデルごとのヘルプテキストカスタマイズのテスト"""

        # テスト用に動的にクラスを作成
        class CustomHelpTextRequest(SimpleRequest):
            class Meta:
                proxy = True  # DBテーブルを作らない
                app_label = "approvals"

            @classmethod
            def get_help_texts(cls):
                return {"title": "カスタムヘルプテキスト"}

        # フォームクラス生成
        FormClass = create_request_form_class(CustomHelpTextRequest)
        form = FormClass()

        # 検証
        self.assertEqual(
            form.fields["title"].help_text, "カスタムヘルプテキスト"
        )

        # デフォルトの挙動も確認（SimpleRequestはオーバーライドしていないはず）
        SimpleFormClass = create_request_form_class(SimpleRequest)
        simple_form = SimpleFormClass()
        self.assertNotEqual(
            simple_form.fields["title"].help_text, "カスタムヘルプテキスト"
        )

    def test_custom_label_in_form(self):
        """モデルごとのラベルカスタマイズのテスト"""

        class CustomLabelRequest(SimpleRequest):
            class Meta:
                proxy = True
                app_label = "approvals"

            @classmethod
            def get_labels(cls):
                return {"title": "カスタムラベル"}

        FormClass = create_request_form_class(CustomLabelRequest)
        form = FormClass()
        self.assertEqual(form.fields["title"].label, "カスタムラベル")

    def test_custom_widget_in_form(self):
        """モデルごとのウィジェットカスタマイズのテスト"""
        from django import forms

        class CustomWidgetRequest(SimpleRequest):
            class Meta:
                proxy = True
                app_label = "approvals"

            @classmethod
            def get_widgets(cls):
                # 通常は Select だが RadioSelect に上書き
                return {"content": forms.RadioSelect()}

        FormClass = create_request_form_class(CustomWidgetRequest)
        form = FormClass()
        self.assertIsInstance(form.fields["content"].widget, forms.RadioSelect)

    def test_m2m_field_in_form(self):
        """ManyToManyField が適切に処理されるかのテスト"""
        from django import forms
        from django.db import models

        from approvals.models import Request

        # M2Mを持つテスト用モデル
        class M2MRequest(Request):
            tags = models.ManyToManyField(
                "auth.Group", blank=True, verbose_name="タグ"
            )

            class Meta:
                app_label = "approvals"

        FormClass = create_request_form_class(M2MRequest)
        form = FormClass()

        # ManyToManyField が SelectMultiple ウィジェット（form-selectクラス付き）になっているか確認
        self.assertIn("tags", form.fields)
        self.assertIsInstance(form.fields["tags"].widget, forms.SelectMultiple)
        self.assertEqual(
            form.fields["tags"].widget.attrs.get("class"), "form-select"
        )

    def test_customize_formfield(self):
        """formfield_callback によるフィールドカスタマイズのテスト"""
        from django import forms
        from django.db import models

        from approvals.models import Request

        class JsonFieldRequest(Request):
            # JSONField を定義
            options = models.JSONField(default=list, blank=True)

            class Meta:
                app_label = "approvals"

            @classmethod
            def customize_formfield(cls, field, **kwargs):
                if field.name == "options":
                    # kwargs に widget が含まれている場合があるため除外する
                    kwargs.pop("widget", None)
                    return forms.MultipleChoiceField(
                        choices=[("A", "Option A"), ("B", "Option B")],
                        widget=forms.CheckboxSelectMultiple,
                        **kwargs,
                    )
                return super().customize_formfield(field, **kwargs)

        FormClass = create_request_form_class(JsonFieldRequest)
        form = FormClass()

        # options フィールドが MultipleChoiceField になっているか
        self.assertIsInstance(
            form.fields["options"], forms.MultipleChoiceField
        )
        # ウィジェットが CheckboxSelectMultiple になっているか
        self.assertIsInstance(
            form.fields["options"].widget, forms.CheckboxSelectMultiple
        )
        # 選択肢が正しいか
        self.assertEqual(
            form.fields["options"].choices,
            [("A", "Option A"), ("B", "Option B")],
        )
