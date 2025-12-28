from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from notification.models import Notification
from approvals.models import SimpleRequest, SimpleApprover, SimpleApprovalLog

User = get_user_model()


class Command(BaseCommand):
    help = '開発用のテストデータを初期投入します'

    def handle(self, *args, **options):
        self.stdout.write("--- テストデータ作成開始 ---")

        # 1. ユーザー作成
        self.create_users()

        # 2. お知らせ作成
        self.create_notifications()

        # 3. 申請データ作成
        self.create_requests()

        self.stdout.write(self.style.SUCCESS("--- テストデータ作成完了 ---"))

    def create_users(self):
        """ユーザー定義と作成"""
        users_data = [
            # 管理者
            {
                "email": "admin@example.com", "last": "管理",
                "first": "者", "role": "admin"
            },
            # 承認者たち
            {
                "email": "bucho@example.com", "last": "田中",
                "first": "部長", "role": "approver"
            },
            {
                "email": "kacho@example.com", "last": "佐藤",
                "first": "課長", "role": "approver"
            },
            {
                "email": "leader@example.com", "last": "鈴木",
                "first": "リーダー", "role": "approver"
            },
            # 一般ユーザー
            {
                "email": "yamada@example.com", "last": "山田",
                "first": "花子", "role": "general"
            },
            {
                "email": "sato@example.com", "last": "佐藤",
                "first": "次郎", "role": "general"
            },
        ]

        for data in users_data:
            if data["role"] == "admin":
                user, created = User.objects.get_or_create(email=data["email"])
                if created:
                    user.set_password("admin")  # 開発用パスワード
                    user.is_staff = True
                    user.is_superuser = True
                    user.is_active = True
                    user.last_name = data["last"]
                    user.first_name = data["first"]
                    user.save()
                    self.stdout.write(f"管理者作成: {user.email}")
            else:
                user, created = User.objects.get_or_create(email=data["email"])
                user.last_name = data["last"]
                user.first_name = data["first"]
                user.is_active = True
                user.is_approver = (data["role"] == "approver")
                user.save()
                if created:
                    display_name = user.get_display_name()
                    role = data['role']
                    self.stdout.write(
                        f"ユーザー作成: {display_name} ({role})"
                    )

    def create_notifications(self):
        """お知らせ作成"""
        notices = [
            {
                "title": "システムメンテナンスのお知らせ",
                "content": "12月31日の23:00からメンテナンスを行います。",
                "days_ago": 0
            },
            {
                "title": "年末年始の営業について",
                "content": "12月29日から1月3日まで休業となります。",
                "days_ago": 2
            },
            {
                "title": "ポポン運用開始",
                "content": "本日より新承認システム「ポポン」が稼働しました。",
                "days_ago": 5
            }
        ]

        for notice in notices:
            pub_date = timezone.now() - timedelta(days=notice["days_ago"])
            n, created = Notification.objects.get_or_create(
                title=notice["title"],
                defaults={
                    "content": notice["content"],
                    "published_at": pub_date
                }
            )
            if created:
                self.stdout.write(f"お知らせ作成: {n.title}")

    def create_requests(self):
        """申請データのバリエーション作成"""
        yamada = User.objects.get(email="yamada@example.com")
        leader = User.objects.get(email="leader@example.com")
        kacho = User.objects.get(email="kacho@example.com")
        bucho = User.objects.get(email="bucho@example.com")

        # 1. 申請中（リーダー承認待ち）
        if not SimpleRequest.objects.filter(
            request_number="REQ-TEST-001"
        ).exists():
            r1 = SimpleRequest.objects.create(
                request_number="REQ-TEST-001",
                applicant=yamada,
                title="PC購入申請",
                content="スペック不足のため買い替えをお願いします。",
                status=SimpleRequest.STATUS_PENDING,
                current_step=1,
                submitted_at=timezone.now()
            )
            SimpleApprover.objects.create(
                request=r1, user=leader, order=1, status=0
            )
            SimpleApprover.objects.create(
                request=r1, user=kacho, order=2, status=0
            )
            self.log(r1, yamada, SimpleApprovalLog.ACTION_SUBMIT, "新規申請")
            self.stdout.write(f"申請作成: {r1.title} (承認待ち)")

        # 2. 申請中（課長承認待ち / リーダー承認済み）
        if not SimpleRequest.objects.filter(
            request_number="REQ-TEST-002"
        ).exists():
            r2 = SimpleRequest.objects.create(
                request_number="REQ-TEST-002",
                applicant=yamada,
                title="出張旅費精算",
                content="大阪出張の交通費です。",
                status=SimpleRequest.STATUS_PENDING,
                current_step=2,
                submitted_at=timezone.now() - timedelta(days=1)
            )
            # リーダー：承認済み
            SimpleApprover.objects.create(
                request=r2, user=leader, order=1, status=1,
                processed_at=timezone.now(), comment="OKです"
            )
            # 課長：未処理
            SimpleApprover.objects.create(
                request=r2, user=kacho, order=2, status=0
            )
            self.log(r2, yamada, SimpleApprovalLog.ACTION_SUBMIT, "新規申請")
            self.log(r2, leader, SimpleApprovalLog.ACTION_APPROVE,
                     "OKです", step=1)
            self.stdout.write(f"申請作成: {r2.title} (進行中)")

        # 3. 承認完了
        if not SimpleRequest.objects.filter(
            request_number="REQ-TEST-003"
        ).exists():
            r3 = SimpleRequest.objects.create(
                request_number="REQ-TEST-003",
                applicant=yamada,
                title="備品購入",
                content="マウスが壊れました。",
                status=SimpleRequest.STATUS_APPROVED,
                current_step=2,
                submitted_at=timezone.now() - timedelta(days=5)
            )
            SimpleApprover.objects.create(
                request=r3, user=leader, order=1, status=1,
                processed_at=timezone.now(), comment="どうぞ"
            )
            self.log(r3, yamada, SimpleApprovalLog.ACTION_SUBMIT, "新規申請")
            self.log(r3, leader, SimpleApprovalLog.ACTION_APPROVE,
                     "どうぞ", step=1)
            self.stdout.write(f"申請作成: {r3.title} (完了)")

        # 4. 閲覧制限付き（部長決裁のみ）
        if not SimpleRequest.objects.filter(
            request_number="REQ-TEST-SEC"
        ).exists():
            r4 = SimpleRequest.objects.create(
                request_number="REQ-TEST-SEC",
                applicant=yamada,
                title="人事に関する相談",
                content="極秘事項です。",
                status=SimpleRequest.STATUS_PENDING,
                is_restricted=True,
                current_step=1,
                submitted_at=timezone.now()
            )
            SimpleApprover.objects.create(
                request=r4, user=bucho, order=1, status=0
            )
            self.log(r4, yamada, SimpleApprovalLog.ACTION_SUBMIT, "新規申請")
            self.stdout.write(f"申請作成: {r4.title} (非公開)")

    def log(self, req, actor, action, comment, step=None):
        SimpleApprovalLog.objects.create(
            request=req, actor=actor, action=action, step=step, comment=comment
        )
