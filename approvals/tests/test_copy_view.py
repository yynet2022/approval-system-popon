from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from approvals.models import Request
from approvals.models.types import SimpleRequest

User = get_user_model()


class RequestCopyViewTest(TestCase):
    """
    申請コピー機能のテスト
    """

    def setUp(self):
        # ユーザーの用意
        self.applicant = User.objects.create_user(
            email="applicant@example.com",
            is_active=True,
            last_name="申",
            first_name="請太郎",
        )
        self.approver1 = User.objects.create_user(
            email="app1@example.com", is_active=True, is_approver=True
        )

        # コピー元の申請を作成
        self.original_request = SimpleRequest.objects.create(
            title="オリジナル申請",
            content="これはオリジナルの内容です",
            applicant=self.applicant,
            status=Request.STATUS_APPROVED,  # 承認済みでもコピー可
            request_number="REQ-ORIGINAL-001",
            is_restricted=True,  # 閲覧制限あり
        )

    def test_copy_view_access(self):
        """コピー画面へのアクセス確認"""
        self.client.force_login(self.applicant)
        url = reverse(
            "approvals:copy", kwargs={"pk": self.original_request.id}
        )
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "簡易承認申請 作成 (コピー)")

        # フォームの初期値に値が入っているか確認
        form = response.context["form"]
        self.assertEqual(form.initial["title"], "オリジナル申請")
        self.assertEqual(form.initial["content"], "これはオリジナルの内容です")

        # is_restricted もコピーされて True になっているはず
        self.assertTrue(form.initial["is_restricted"])

    def test_copy_and_create_new_request(self):
        """コピーして新規作成を実行"""
        self.client.force_login(self.applicant)
        url = reverse(
            "approvals:copy", kwargs={"pk": self.original_request.id}
        )

        # POSTデータ（コピー内容を一部変更して送信）
        # is_restricted は True のまま送信してみる
        data = {
            "title": "コピー申請",  # 変更
            "content": "これはオリジナルの内容です",  # そのまま
            "is_restricted": True,
            "approvers-TOTAL_FORMS": "1",
            "approvers-INITIAL_FORMS": "0",
            "approvers-0-user": str(self.approver1.id),
            "approvers-0-order": "1",
        }

        response = self.client.post(url, data, follow=True)
        self.assertContains(
            response, "申請 REQ-S-"
        )  # 成功メッセージに含まれるはず

        # DB確認
        # 新しい申請が作られているか
        new_req = SimpleRequest.objects.get(title="コピー申請")
        self.assertEqual(new_req.content, "これはオリジナルの内容です")
        self.assertEqual(new_req.applicant, self.applicant)
        self.assertEqual(new_req.status, Request.STATUS_PENDING)

        # is_restricted が True であること
        self.assertTrue(new_req.is_restricted)

        # IDや申請番号が別物であること
        self.assertNotEqual(new_req.id, self.original_request.id)
        self.assertNotEqual(
            new_req.request_number, self.original_request.request_number
        )

    def test_copy_view_404(self):
        """存在しない申請IDを指定した場合"""
        self.client.force_login(self.applicant)
        import uuid

        dummy_uuid = uuid.uuid4()
        url = reverse("approvals:copy", kwargs={"pk": dummy_uuid})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
