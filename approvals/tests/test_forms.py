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
