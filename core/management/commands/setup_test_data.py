from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from approvals.models import (
    ApprovalLog,
    Approver,
    Request,
)
from approvals.models.types import (
    LocalBusinessTripRequest,
    SimpleRequest,
)
from notification.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = "開発用のテストデータを網羅的に投入します"

    def handle(self, *args, **options):
        self.stdout.write("--- テストデータ作成開始 ---")

        # 1. ユーザー作成
        self.create_users()

        # 2. お知らせ作成
        self.create_notifications()

        # 3. 申請データ作成 (簡易申請)
        self.create_simple_requests()

        # 4. 申請データ作成 (近距離出張申請)
        self.create_trip_requests()

        # 5. 大量データ作成 (ページネーション確認用)
        self.create_bulk_requests()

        self.stdout.write(self.style.SUCCESS("--- テストデータ作成完了 ---"))

    def create_users(self):
        """ユーザー定義と作成"""
        users_data = [
            # 管理者
            {
                "email": "admin@example.com",
                "last": "管理",
                "first": "者",
                "role": "admin",
            },
            # 承認者たち
            {
                "email": "bucho@example.com",
                "last": "田中",
                "first": "部長",
                "role": "approver",
            },
            {
                "email": "kacho@example.com",
                "last": "佐藤",
                "first": "課長",
                "role": "approver",
            },
            {
                "email": "leader@example.com",
                "last": "鈴木",
                "first": "リーダー",
                "role": "approver",
            },
            # 一般ユーザー
            {
                "email": "yamada@example.com",
                "last": "山田",
                "first": "花子",
                "role": "general",
            },
            {
                "email": "sato@example.com",
                "last": "佐藤",
                "first": "次郎",
                "role": "general",
            },
        ]

        for data in users_data:
            user, created = User.objects.get_or_create(email=data["email"])
            user.last_name = data["last"]
            user.first_name = data["first"]
            user.is_active = True

            if data["role"] == "admin":
                user.is_staff = True
                # user.is_superuser = True
                if created:
                    user.set_password("adminxxx")

            user.is_approver = (
                data["role"] == "approver"  # or data["role"] == "admin"
            )
            user.save()

            if created:
                role_display = (
                    "管理者"
                    if data["role"] == "admin"
                    else "承認者" if data["role"] == "approver" else "一般"
                )
                self.stdout.write(
                    f"ユーザー作成: {user.get_display_name()} ({role_display})"
                )

    def create_notifications(self):
        """お知らせ作成"""
        # 今日 (2025-12-30) を基準にする
        base_date = timezone.make_aware(datetime(2025, 12, 30))

        notices = [
            {
                "title": "あけましておめでとうございます",
                "content": "本年もよろしくお願いします。",
                "days_ago": -1,  # 未来 (12/31)
            },
            {
                "title": "システムメンテナンスのお知らせ",
                "content": "12月31日の23:00からメンテナンスを行います。",
                "days_ago": 1,
            },
            {
                "title": "年末年始の営業について",
                "content": "12月29日から1月3日まで休業となります。",
                "days_ago": 2,
            },
            {
                "title": "近距離出張申請",
                "content": "本日より近距離出張申請が可能になりました。",
                "days_ago": 3,
            },
            {
                "title": "差戻し機能",
                "content": "差し戻された申請は取り下げるか再申請が可能です。",
                "days_ago": 4,
            },
            {
                "title": "承認者について",
                "content": "デフォルトは2人ですが、5人まで増やせます。",
                "days_ago": 5,
            },
            {
                "title": "ポポン運用開始",
                "content": "本日より新承認システム「ポポン」が稼働しました。",
                "days_ago": 6,
            },
            {
                "title": "旧システムのデータ移行について",
                "content": "旧システムのデータは1月末まで閲覧可能です。",
                "days_ago": 7,
            },
        ]

        for notice in notices:
            pub_date = base_date - timedelta(days=notice["days_ago"])
            n, created = Notification.objects.update_or_create(
                title=notice["title"],
                defaults={
                    "content": notice["content"],
                    "published_at": pub_date,
                },
            )
            if created:
                self.stdout.write(f"お知らせ作成: {n.title}")

    def create_simple_requests(self):
        """簡易申請のバリエーション"""
        yamada = User.objects.get(email="yamada@example.com")
        leader = User.objects.get(email="leader@example.com")
        kacho = User.objects.get(email="kacho@example.com")
        bucho = User.objects.get(email="bucho@example.com")

        # 1. 申請中（リーダー承認待ち）
        self.make_simple(
            "REQ-S-TEST-0001",
            yamada,
            "PC購入申請",
            "スペック不足のため買い替えをお願いします。",
            Request.STATUS_PENDING,
            1,
            [(leader, 0), (kacho, 0)],
        )

        # 2. 申請中（課長承認待ち / リーダー承認済み）
        self.make_simple(
            "REQ-S-TEST-0002",
            yamada,
            "出張旅費精算",
            "大阪出張の交通費です。",
            Request.STATUS_PENDING,
            2,
            [(leader, 1, "OKです"), (kacho, 0)],
        )

        # 3. 承認完了
        self.make_simple(
            "REQ-S-TEST-0003",
            yamada,
            "備品購入",
            "マウスが壊れました。",
            Request.STATUS_APPROVED,
            2,
            [(leader, 1, "どうぞ")],
        )

        # 4. 閲覧制限付き（部長決裁のみ）
        self.make_simple(
            "REQ-S-TEST-0004",
            yamada,
            "人事に関する相談",
            "極秘事項です。",
            Request.STATUS_PENDING,
            1,
            [(bucho, 0)],
            is_restricted=True,
        )

        # 5. 却下（佐藤課長が却下）
        self.make_simple(
            "REQ-S-TEST-0005",
            yamada,
            "高級家具購入",
            "オフィス用ソファ。",
            Request.STATUS_REJECTED,
            1,
            [(kacho, 9, "予算オーバーです")],
        )

        # 6. 差戻し（鈴木リーダーから）
        self.make_simple(
            "REQ-S-TEST-0006",
            yamada,
            "研修参加希望",
            "Pythonセミナー。",
            Request.STATUS_REMANDED,
            1,
            [(leader, 2, "詳細希望")],
        )

    def create_trip_requests(self):
        """近距離出張申請の網羅データ追加"""
        sato_j = User.objects.get(email="sato@example.com")  # 佐藤次郎さん
        yamada = User.objects.get(email="yamada@example.com")
        leader = User.objects.get(email="leader@example.com")
        kacho = User.objects.get(email="kacho@example.com")
        bucho = User.objects.get(email="bucho@example.com")

        # 1. 申請中（佐藤課長待ち）
        self.make_trip(
            "REQ-L-TEST-0001",
            sato_j,
            "大阪支社訪問",
            date(2026, 1, 10),
            "大阪支社",
            "定例会議",
            Request.STATUS_PENDING,
            1,
            [(kacho, 0)],
        )

        # 2. 承認完了（部長まで）
        self.make_trip(
            "REQ-L-TEST-0002",
            yamada,
            "名古屋工場視察",
            date(2025, 12, 20),
            "名古屋工場",
            "現場確認",
            Request.STATUS_APPROVED,
            3,
            [(kacho, 1, "OK"), (bucho, 1, "承認")],
        )

        # 3. 差戻し (田中部長から)
        self.make_trip(
            "REQ-L-TEST-0003",
            yamada,
            "京都営業所訪問",
            date(2026, 2, 1),
            "京都営業所",
            "同行",
            Request.STATUS_REMANDED,
            2,
            [(kacho, 1), (bucho, 2, "同行者名を入れて")],
        )

        # 4. 取り下げ
        self.make_trip(
            "REQ-L-TEST-0004",
            sato_j,
            "不要な申請",
            date(2026, 3, 1),
            "不明",
            "テスト",
            Request.STATUS_WITHDRAWN,
            1,
            [(leader, 0)],
        )

    def create_bulk_requests(self):
        """大量のダミー申請データを作成（ページネーション確認用）"""
        sato_j = User.objects.get(email="sato@example.com")
        yamada = User.objects.get(email="yamada@example.com")
        leader = User.objects.get(email="leader@example.com")
        kacho = User.objects.get(email="kacho@example.com")

        self.stdout.write("大量申請データ作成中...")
        for i in range(1, 26):
            applicant = yamada if i % 2 == 0 else sato_j
            num = f"REQ-BULK-{i:04d}"
            self.make_simple(
                num,
                applicant,
                f"大量テスト申請 {i}",
                f"これはページネーションテスト用のダミーデータ第 {i} 号です。",
                Request.STATUS_APPROVED,
                2,
                [(leader, 1, "OK"), (kacho, 1, "承認")],
            )

    def make_simple(
        self,
        num,
        applicant,
        title,
        content,
        status,
        step,
        route,
        is_restricted=False,
    ):
        """SimpleRequest作成補助"""
        if Request.objects.filter(request_number=num).exists():
            return
        req = SimpleRequest.objects.create(
            request_number=num,
            applicant=applicant,
            title=title,
            content=content,
            status=status,
            current_step=step,
            is_restricted=is_restricted,
            submitted_at=timezone.now() - timedelta(hours=1),
        )
        self._set_route(req, applicant, route)
        self.stdout.write(f"簡易申請作成: {title} (No: {num})")

    def make_trip(
        self,
        num,
        applicant,
        title,
        t_date,
        dest,
        note,
        status,
        step,
        route,
        is_restricted=False,
    ):
        """LocalBusinessTripRequest作成補助"""
        if Request.objects.filter(request_number=num).exists():
            return
        req = LocalBusinessTripRequest.objects.create(
            request_number=num,
            applicant=applicant,
            title=title,
            trip_date=t_date,
            destination=dest,
            note=note,
            status=status,
            current_step=step,
            is_restricted=is_restricted,
            submitted_at=timezone.now() - timedelta(hours=2),
        )
        self._set_route(req, applicant, route)
        self.stdout.write(f"出張申請作成: {title} (No: {num})")

    def _set_route(self, req, applicant, route):
        """承認ルートとログの作成"""
        # 申請ログ
        ApprovalLog.objects.create(
            request=req,
            actor=applicant,
            action=ApprovalLog.ACTION_SUBMIT,
            step=None,
            comment="新規申請",
        )

        for i, data in enumerate(route, start=1):
            user = data[0]
            status = data[1]
            comment = data[2] if len(data) > 2 else ""

            Approver.objects.create(
                request=req,
                user=user,
                order=i,
                status=status,
                comment=comment,
                processed_at=timezone.now() if status != 0 else None,
            )

            if status != 0:
                action = (
                    ApprovalLog.ACTION_APPROVE
                    if status == 1
                    else (
                        ApprovalLog.ACTION_REMAND
                        if status == 2
                        else ApprovalLog.ACTION_REJECT if status == 9 else None
                    )
                )
                if action:
                    ApprovalLog.objects.create(
                        request=req,
                        actor=user,
                        action=action,
                        step=i,
                        comment=comment,
                    )

        # 最終的な取下ログなど
        if req.status == Request.STATUS_WITHDRAWN:
            ApprovalLog.objects.create(
                request=req,
                actor=applicant,
                action=ApprovalLog.ACTION_WITHDRAW,
                step=None,
                comment="取り下げます",
            )

    def log(self, req, actor, action, comment, step=None):
        """互換性のためのヘルパー（ApprovalLogを使用）"""
        ApprovalLog.objects.create(
            request=req, actor=actor, action=action, step=step, comment=comment
        )
