from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from approvals.models import Approver
from approvals.models.types import SimpleRequest

User = get_user_model()


class SendApprovalRemindersTest(TestCase):
    def setUp(self):
        # ユーザー作成
        self.applicant = User.objects.create_user(
            email="applicant@example.com"
        )
        self.approver_a = User.objects.create_user(
            email="approver_a@example.com"
        )
        self.approver_b = User.objects.create_user(
            email="approver_b@example.com"
        )

        # 時間の基準
        self.now = timezone.now()
        self.old_time = self.now - timedelta(hours=25)
        self.recent_time = self.now - timedelta(hours=1)

    def create_request(
        self,
        title,
        applicant,
        approver,
        updated_at,
        status=SimpleRequest.STATUS_PENDING,
    ):
        # Request作成
        req = SimpleRequest.objects.create(
            request_number=f"REQ-{title}",  # 簡易的にタイトルを番号に
            title=title,
            applicant=applicant,
            status=status,
            content="test content",
            submitted_at=updated_at,  # 申請日時は適当に
        )

        # Approver作成
        Approver.objects.create(
            request=req, user=approver, order=1, status=Approver.STATUS_PENDING
        )

        # updated_at を強制更新（auto_now=Trueのため、save後にupdateが必要）
        SimpleRequest.objects.filter(pk=req.pk).update(updated_at=updated_at)
        req.refresh_from_db()
        return req

    def test_send_reminders(self):
        # 1. 対象外: 最近の申請
        self.create_request(
            "recent", self.applicant, self.approver_a, self.recent_time
        )

        # 2. 対象外: 既に承認済みの古い申請
        req_approved = self.create_request(
            "approved",
            self.applicant,
            self.approver_a,
            self.old_time,
            status=SimpleRequest.STATUS_APPROVED,
        )
        # Approverの状態も更新しておく（コマンドロジックはRequestステータスとApproverの存在を見るが、念のため）
        Approver.objects.filter(request=req_approved).update(
            status=Approver.STATUS_APPROVED
        )

        # 3. 対象: 古いPending申請 (承認者A) - 1
        self.create_request(
            "old_a_1", self.applicant, self.approver_a, self.old_time
        )

        # 4. 対象: 古いPending申請 (承認者A) - 2
        self.create_request(
            "old_a_2",
            self.applicant,
            self.approver_a,
            self.old_time - timedelta(hours=1),
        )

        # 5. 対象: 古いPending申請 (承認者B)
        self.create_request(
            "old_b", self.applicant, self.approver_b, self.old_time
        )

        # コマンド実行
        out = StringIO()
        call_command("send_approval_reminders", stdout=out)

        # 検証
        self.assertEqual(
            len(mail.outbox), 2, "Emails should be sent to approver A and B"
        )

        # 承認者A宛のメール確認
        email_a = next(
            (e for e in mail.outbox if self.approver_a.email in e.to), None
        )
        self.assertIsNotNone(email_a)
        self.assertIn("Reminder", email_a.subject)
        self.assertIn("old_a_1", email_a.body)
        self.assertIn("old_a_2", email_a.body)
        self.assertNotIn("old_b", email_a.body)  # Bの申請は含まれない
        self.assertNotIn("recent", email_a.body)  # 最近の申請は含まれない
        self.assertIn("http", email_a.body)  # URLが含まれているか

        # 標準出力確認
        output = out.getvalue()
        self.assertIn("Found 3 stalled requests", output)

    def test_dry_run(self):
        # 1. 対象の申請を作成
        self.create_request(
            "old_dry", self.applicant, self.approver_a, self.old_time
        )

        # コマンド実行 (dry-run)
        out = StringIO()
        call_command("send_approval_reminders", dry_run=True, stdout=out)

        # 検証: メールが送信されていないこと
        self.assertEqual(len(mail.outbox), 0)

        # 標準出力に内容が出ていること
        output = out.getvalue()
        self.assertIn("--- DRY RUN MODE ---", output)
        self.assertIn("Would send email to: approver_a@example.com", output)
        self.assertIn("old_dry", output)
        self.assertIn("--- DRY RUN COMPLETED ---", output)
