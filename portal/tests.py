# portal/tests.py
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from approvals.models import Approver, Request
from approvals.models.types import SimpleRequest


class PortalViewTest(TestCase):
    """
    ポータル画面の表示テスト。
    """
    def setUp(self):
        self.user = User.objects.create_user(
            email="portal@example.com", is_active=True
        )
        self.approver = User.objects.create_user(
            email="approver@example.com", is_active=True, is_approver=True
        )

    def test_dashboard_pending_approvals(self):
        """「承認依頼」エリアの表示テスト"""
        req = SimpleRequest.objects.create(
            title="自分宛の依頼", applicant=self.user,
            status=Request.STATUS_PENDING, request_number="REQ-P1"
        )
        Approver.objects.create(
            request=req, user=self.approver, order=1
        )

        self.client.force_login(self.approver)
        url = reverse("portal:index")
        response = self.client.get(url)

        self.assertContains(response, "自分宛の依頼")

    def test_search_and_filter(self):
        """検索機能とステータスフィルタのテスト"""
        # データ準備
        SimpleRequest.objects.create(
            title="承認済みりんご", applicant=self.user,
            status=Request.STATUS_APPROVED, request_number="REQ-AP"
        )
        SimpleRequest.objects.create(
            title="申請中みかん", applicant=self.user,
            status=Request.STATUS_PENDING, request_number="REQ-PE"
        )

        url = reverse("portal:index")

        # キーワード検索
        res_q = self.client.get(url, {"q": "りんご"})
        self.assertContains(res_q, "承認済みりんご")
        self.assertNotContains(res_q, "申請中みかん")

        # ステータスフィルタ
        status_approved = str(Request.STATUS_APPROVED)
        res_s = self.client.get(url, {"status": status_approved})
        self.assertContains(res_s, "承認済みりんご")
        self.assertNotContains(res_s, "申請中みかん")

    def test_restricted_list_view(self):
        """一覧画面での閲覧制限テスト"""
        # 公開の申請
        SimpleRequest.objects.create(
            title="みんな見てね", applicant=self.user,
            is_restricted=False, request_number="REQ-PUB"
        )
        # 非公開の申請（作成者は self.user）
        SimpleRequest.objects.create(
            title="秘密だよ", applicant=self.user,
            is_restricted=True, request_number="REQ-SEC"
        )

        # 第三者（approver）でログイン
        # approver は secret_req の承認ルートに入っていないので見えないはず
        self.client.force_login(self.approver)
        url = reverse("portal:index")
        response = self.client.get(url)

        self.assertContains(response, "みんな見てね")
        self.assertNotContains(response, "秘密だよ")

        # ちなみに、作成者（self.user）なら見えるはず
        self.client.force_login(self.user)
        response_owner = self.client.get(url)
        self.assertContains(response_owner, "秘密だよ")
