# accounts/tests.py
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginToken, User


class UserAuthTest(TestCase):
    """
    認証周りのテスト。
    """

    def setUp(self):
        self.email = "test@example.com"

    def test_create_user(self):
        """ユーザー作成のテスト"""
        user = User.objects.create_user(email=self.email)
        self.assertEqual(user.email, self.email)
        self.assertFalse(user.is_active)
        self.assertFalse(user.has_usable_password())

    def test_create_superuser(self):
        """管理者ユーザー作成のテスト"""
        admin = User.objects.create_superuser(email="admin@example.com")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)

    def test_get_display_name(self):
        """表示名ロジックのテスト"""
        # ケース1: メアドのみ
        u1 = User(email="only@example.com")
        self.assertEqual(u1.get_display_name(), "only@example.com")

        # ケース2: 姓名あり
        u2 = User(
            email="full@example.com", last_name="山田", first_name="太郎"
        )
        self.assertEqual(u2.get_display_name(), "山田 太郎")

        # ケース3: 姓のみ
        u3 = User(email="last@example.com", last_name="佐藤")
        self.assertEqual(u3.get_display_name(), "佐藤")

    def test_verify_token_view(self):
        """トークン検証ビューの正常系テスト"""
        user = User.objects.create_user(email=self.email)
        token_record = LoginToken.create_token(user)

        url = reverse("accounts:verify", kwargs={"token": token_record.token})
        response = self.client.get(url)

        self.assertRedirects(response, reverse("portal:index"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertFalse(
            LoginToken.objects.filter(id=token_record.id).exists()
        )

    def test_verify_invalid_token(self):
        """トークン検証ビューの異常系テスト"""
        # ケース1: 存在しないトークン
        url = reverse("accounts:verify", kwargs={"token": "fake-token"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)  # エラー画面

        # ケース2: 期限切れトークン
        user = User.objects.create_user(email="expired@example.com")
        token_record = LoginToken.create_token(user)
        # 過去へ
        token_record.expires_at = timezone.now() - timedelta(minutes=1)
        token_record.save()

        url_exp = reverse(
            "accounts:verify", kwargs={"token": token_record.token}
        )
        response = self.client.get(url_exp)
        self.assertEqual(response.status_code, 400)
