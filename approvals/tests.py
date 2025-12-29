# approvals/tests.py
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.core import mail
from accounts.models import User
from .models import Approver, LocalBusinessTripRequest, Request, SimpleRequest
import logging


class ApprovalWorkflowTest(TestCase):
    """
    承認ワークフローのテスト。
    """
    def setUp(self):
        # ユーザーの用意
        self.applicant = User.objects.create_user(
            email="applicant@example.com",
            is_active=True,
            last_name="申",
            first_name="請太郎"
        )
        self.approver1 = User.objects.create_user(
            email="app1@example.com", is_active=True, is_approver=True
        )
        self.approver2 = User.objects.create_user(
            email="app2@example.com", is_active=True, is_approver=True
        )
        self.staff = User.objects.create_user(
            email="staff@example.com", is_active=True, is_staff=True
        )

    def test_create_trip_request(self):
        """近距離出張申請の作成テスト"""
        self.client.force_login(self.applicant)
        url = reverse("approvals:create", kwargs={"request_type": "trip"})
        data = {
            "title": "大阪出張",
            "trip_date": "2025-12-30",
            "destination": "大阪支社",
            "note": "日帰り",
            "approvers-TOTAL_FORMS": "1", "approvers-INITIAL_FORMS": "0",
            "approvers-0-user": str(self.approver1.id),
            "approvers-0-order": "1",
        }
        response = self.client.post(url, data, follow=True)
        self.assertContains(response, "大阪出張")

        # DB確認
        req = LocalBusinessTripRequest.objects.get(title="大阪出張")
        self.assertEqual(req.destination, "大阪支社")
        self.assertEqual(str(req.trip_date), "2025-12-30")
        self.assertEqual(req.status, Request.STATUS_PENDING)

    def test_create_request_validation(self):
        """申請作成時のバリデーションテスト"""
        self.client.force_login(self.applicant)
        url = reverse("approvals:create", kwargs={"request_type": "simple"})

        # ケース1: 承認者が自分自身
        data_self = {
            "title": "自分承認", "content": "ダメ",
            "approvers-TOTAL_FORMS": "1", "approvers-INITIAL_FORMS": "0",
            "approvers-0-user": str(self.applicant.id),
            "approvers-0-order": "1",
        }
        response = self.client.post(url, data_self)
        self.assertContains(
            response, "申請者本人を承認者に含めることはできません"
        )

        # ケース2: 同じ承認者が連続
        data_dup = {
            "title": "連続承認", "content": "ダメ",
            "approvers-TOTAL_FORMS": "2", "approvers-INITIAL_FORMS": "0",
            "approvers-0-user": str(self.approver1.id),
            "approvers-0-order": "1",
            "approvers-1-user": str(self.approver1.id),
            "approvers-1-order": "2",
        }
        response = self.client.post(url, data_dup)
        self.assertContains(
            response, "同じ承認者を連続して設定することはできません"
        )

    def test_create_request_success_and_mail(self):
        """申請作成成功とメール件名確認"""
        self.client.force_login(self.applicant)
        url = reverse("approvals:create", kwargs={"request_type": "simple"})
        data = {
            "title": "メール確認用", "content": "内容は問わない",
            "approvers-TOTAL_FORMS": "1", "approvers-INITIAL_FORMS": "0",
            "approvers-0-user": str(self.approver1.id),
            "approvers-0-order": "1",
        }
        self.client.post(url, data)

        # メール送信確認
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(f"[{settings.PROJECT_NAME}]", mail.outbox[0].subject)
        self.assertIn("承認依頼", mail.outbox[0].subject)

    def test_reject_action(self):
        """却下アクションのテスト"""
        req = SimpleRequest.objects.create(
            title="却下テスト", applicant=self.applicant,
            status=Request.STATUS_PENDING, request_number="REQ-REJ"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        # コメントなしで却下しようとするとエラー
        self.client.post(action_url, {"action": "reject", "comment": ""})
        req.refresh_from_db()
        self.assertNotEqual(req.status, Request.STATUS_REJECTED)

        # コメントありで却下
        mail.outbox = []  # 前のメールをクリア
        self.client.post(
            action_url, {"action": "reject", "comment": "これはダメ"}
        )
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_REJECTED)

        # メール確認（申請者 + 承認者本人の1通）
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(any("却下" in m.subject for m in mail.outbox))

    def test_withdraw_action(self):
        """取り下げアクションのテスト"""
        req = SimpleRequest.objects.create(
            title="取り下げテスト", applicant=self.applicant,
            status=Request.STATUS_PENDING, request_number="REQ-WD"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        # 申請者ログイン
        self.client.force_login(self.applicant)
        withdraw_url = reverse("approvals:withdraw", kwargs={"pk": req.id})
        self.client.post(withdraw_url)

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_WITHDRAWN)

        # 他人（approver1）は取り下げできない
        req.status = Request.STATUS_PENDING
        req.save()
        self.client.force_login(self.approver1)
        self.client.post(withdraw_url)
        req.refresh_from_db()
        # 変わってないはず
        self.assertEqual(req.status, Request.STATUS_PENDING)

    def test_proxy_remand_action(self):
        """管理者による代理差戻しテスト"""
        req = SimpleRequest.objects.create(
            title="代理差戻し", applicant=self.applicant,
            status=Request.STATUS_PENDING, request_number="REQ-PROXY"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        url = reverse("approvals:proxy-remand", kwargs={"pk": req.id})

        # 一時的に黙らせる。PermissionDenied はウザい
        logger = logging.getLogger('django.request')
        previous_level = logger.getEffectiveLevel()
        logger.setLevel(logging.CRITICAL)
        # 一般ユーザー（approver1）ではアクセス不可
        self.client.force_login(self.approver1)
        response = self.client.post(url, {"comment": "強制"})
        logger.setLevel(previous_level)
        self.assertEqual(response.status_code, 403)  # Forbidden

        # 管理者ならOK
        mail.outbox = []
        self.client.force_login(self.staff)
        self.client.post(url, {"comment": "管理権限で行使"})

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_REMANDED)

        # メール確認（申請者 + 承認者の2通）
        self.assertTrue(any("代理差戻し" in m.subject for m in mail.outbox))

    def test_restricted_access(self):
        """閲覧制限のテスト"""
        req = SimpleRequest.objects.create(
            title="秘密の申請", applicant=self.applicant,
            is_restricted=True, status=Request.STATUS_PENDING,
            request_number="REQ-SEC"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        # 関係者以外（approver2）でログイン
        self.client.force_login(self.approver2)
        url = reverse("approvals:detail", kwargs={"pk": req.id})
        response = self.client.get(url)

        # テンプレート側で permission_denied フラグが立っているか
        self.assertTrue(response.context["permission_denied"])
        self.assertContains(response, "閲覧権限がありません")

    def test_approve_action_workflow(self):
        """承認ワークフロー（中間承認 -> 最終承認）のテスト"""
        # 申請作成（2段階承認）
        req = SimpleRequest.objects.create(
            title="多段階承認", applicant=self.applicant,
            status=Request.STATUS_PENDING, request_number="REQ-MULTI"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )
        Approver.objects.create(
            request=req, user=self.approver2, order=2
        )

        # 1. 最初の承認者による承認
        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})
        self.client.post(action_url, {"action": "approve"})

        req.refresh_from_db()
        self.assertEqual(req.current_step, 2)
        self.assertEqual(req.status, Request.STATUS_PENDING)

        # メール確認（次の承認者へ）
        self.assertIn("承認依頼", mail.outbox[-1].subject)

        # 2. 最終承認者による承認
        self.client.force_login(self.approver2)
        self.client.post(action_url, {"action": "approve"})

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)  # 完了

        # メール確認（完了通知：申請者 + 全承認者に飛ぶ）
        self.assertTrue(any("承認完了" in m.subject for m in mail.outbox))

    def test_remand_action(self):
        """差戻しアクションのテスト"""
        req = SimpleRequest.objects.create(
            title="差戻しテスト", applicant=self.applicant,
            status=Request.STATUS_PENDING, request_number="REQ-REM"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        # コメント必須チェック
        response = self.client.post(
            action_url, {"action": "remand", "comment": ""}
        )
        # コメント必須エラーでリダイレクトされるか、元の画面に戻るか
        # 実装上は redirect("approvals:detail") になる
        self.assertEqual(response.status_code, 302)

        req.refresh_from_db()
        self.assertNotEqual(req.status, Request.STATUS_REMANDED)

        # 正常な差戻し
        self.client.post(
            action_url, {"action": "remand", "comment": "やり直し"}
        )

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_REMANDED)

        # Approverの状態確認
        approver = Approver.objects.get(request=req, user=self.approver1)
        self.assertEqual(approver.status, Approver.STATUS_REMANDED)

    def test_resubmit_action(self):
        """再申請アクションのテスト"""
        # 差戻し状態の申請を作成
        req = SimpleRequest.objects.create(
            title="再申請テスト", applicant=self.applicant,
            status=Request.STATUS_REMANDED, request_number="REQ-RESUB",
            current_step=1
        )
        app_rec = Approver.objects.create(
            request=req, user=self.approver1, order=1,
            status=Approver.STATUS_REMANDED
        )

        self.client.force_login(self.applicant)
        update_url = reverse("approvals:update", kwargs={"pk": req.id})

        # ルート変更なしで再申請
        data = {
            "title": "修正しました", "content": "修正内容",
            "approvers-TOTAL_FORMS": "1", "approvers-INITIAL_FORMS": "1",
            "approvers-MIN_NUM_FORMS": "0",
            "approvers-MAX_NUM_FORMS": "1000",
            "approvers-0-id": str(app_rec.id),
            "approvers-0-user": str(self.approver1.id),
            "approvers-0-order": "1",
        }
        response = self.client.post(update_url, data)

        # リダイレクト確認（成功時は詳細画面等へ）
        self.assertEqual(response.status_code, 302)

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING)
        self.assertEqual(req.current_step, 1)

        # 古いレコードは削除されているはずなので、refreshしようとするとエラーになることを確認
        with self.assertRaises(Approver.DoesNotExist):
            app_rec.refresh_from_db()

        # 新しいレコードが作成され、ステータスがPendingになっていることを確認
        new_approver = Approver.objects.get(
            request=req, user=self.approver1)
        self.assertEqual(new_approver.status, Approver.STATUS_PENDING)
        # IDが変わっていることも確認（再作成の証拠）
        self.assertNotEqual(new_approver.id, app_rec.id)

    def test_approve_already_withdrawn(self):
        """取り下げ済みの申請に対する承認試行のテスト"""
        req = SimpleRequest.objects.create(
            title="入れ違いテスト", applicant=self.applicant,
            status=Request.STATUS_WITHDRAWN,
            request_number="REQ-CONFLICT1"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        # 承認を試みる（リダイレクトを追跡）
        response = self.client.post(
            action_url, {"action": "approve"}, follow=True
        )

        # エラーメッセージの確認
        self.assertContains(
            response, "この申請は既に処理されているか、取り下げられています。"
        )

        req.refresh_from_db()
        self.assertEqual(
            req.status, Request.STATUS_WITHDRAWN
        )  # 変わっていないこと

    def test_approve_already_approved(self):
        """既に承認済みの申請に対する承認試行のテスト"""
        req = SimpleRequest.objects.create(
            title="二重承認テスト", applicant=self.applicant,
            status=Request.STATUS_APPROVED,
            request_number="REQ-CONFLICT2"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1
        )

        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        response = self.client.post(
            action_url, {"action": "approve"}, follow=True
        )

        self.assertContains(
            response, "この申請は既に処理されているか、取り下げられています。"
        )

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)

    def test_withdraw_from_remanded(self):
        """差戻し状態からの取り下げテスト"""
        # 差戻し状態の申請を作成
        req = SimpleRequest.objects.create(
            title="差戻し取り下げテスト", applicant=self.applicant,
            status=Request.STATUS_REMANDED,
            request_number="REQ-REM-WD"
        )
        # 承認者（差戻しを実行したという想定）
        Approver.objects.create(
            request=req, user=self.approver1, order=1,
            status=Approver.STATUS_REMANDED
        )

        # メールボックスをクリア（ここまでの通知などは無視）
        mail.outbox = []

        # 申請者ログイン
        self.client.force_login(self.applicant)
        withdraw_url = reverse("approvals:withdraw", kwargs={"pk": req.id})

        # 取り下げ実行
        self.client.post(withdraw_url)

        req.refresh_from_db()

        # 検証1: ステータスが取り下げになっているか
        self.assertEqual(req.status, Request.STATUS_WITHDRAWN)

        # 検証2: 承認者データが物理削除されていないか
        self.assertEqual(req.approvers.count(), 1)

        # 検証3: メールが送信されていないか
        self.assertEqual(len(mail.outbox), 0)

    def test_reject_after_approval(self):
        """承認完了後の事後却下テスト"""
        req = SimpleRequest.objects.create(
            title="事後却下", applicant=self.applicant,
            status=Request.STATUS_APPROVED,  # 既に承認済み
            request_number="REQ-POST-REJ"
        )
        Approver.objects.create(
            request=req, user=self.approver1, order=1,
            status=Approver.STATUS_APPROVED
        )

        self.client.force_login(self.approver1)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        # 事後却下実行
        self.client.post(
            action_url, {"action": "reject", "comment": "やっぱりダメ"}
        )

        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_REJECTED)

    def test_approve_skip_order(self):
        """順番抜かし承認の防止テスト"""
        req = SimpleRequest.objects.create(
            title="順序テスト", applicant=self.applicant,
            status=Request.STATUS_PENDING,
            request_number="REQ-ORDER",
            current_step=1
        )
        # 1番目: approver1 (未承認)
        Approver.objects.create(
            request=req, user=self.approver1, order=1,
            status=Approver.STATUS_PENDING
        )
        # 2番目: approver2 (未承認)
        Approver.objects.create(
            request=req, user=self.approver2, order=2,
            status=Approver.STATUS_PENDING
        )

        # 2番目の人(approver2)が無理やり承認を試みる
        self.client.force_login(self.approver2)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        response = self.client.post(
            action_url, {"action": "approve"}, follow=True
        )

        # エラーメッセージなどで弾かれているか確認
        self.assertContains(response, "権限がありません")

        req.refresh_from_db()
        # ステップが進んでいないこと
        self.assertEqual(req.current_step, 1)
        # ステータスが変わっていないこと
        self.assertEqual(req.status, Request.STATUS_PENDING)

    def test_reject_skip_order(self):
        """順番抜かし却下の防止テスト"""
        req = SimpleRequest.objects.create(
            title="順序テスト(却下)", applicant=self.applicant,
            status=Request.STATUS_PENDING,
            request_number="REQ-ORDER-REJ",
            current_step=1
        )
        # 1番目: approver1 (未承認)
        Approver.objects.create(
            request=req, user=self.approver1, order=1,
            status=Approver.STATUS_PENDING
        )
        # 2番目: approver2 (未承認)
        Approver.objects.create(
            request=req, user=self.approver2, order=2,
            status=Approver.STATUS_PENDING
        )

        # 2番目の人(approver2)が無理やり却下を試みる
        self.client.force_login(self.approver2)
        action_url = reverse("approvals:action", kwargs={"pk": req.id})

        # 現状の実装だとこれが通ってしまう可能性がある
        response = self.client.post(
            action_url, {"action": "reject", "comment": "フライング却下"},
            follow=True
        )

        # エラーになるべき
        self.assertContains(response, "権限がありません")

        req.refresh_from_db()
        # ステータスが変わっていないこと(Pendingのまま)
        self.assertEqual(req.status, Request.STATUS_PENDING)
