from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Notification

User = get_user_model()


class NotificationTest(TestCase):
    """
    お知らせ機能のテスト。
    """

    def setUp(self):
        # 未来のお知らせ
        self.future_notice = Notification.objects.create(
            title="未来のお知らせ",
            content="まだ見えへんはずやで",
            published_at=timezone.now() + timedelta(days=1),
        )
        # 過去のお知らせ
        self.past_notice = Notification.objects.create(
            title="過去のお知らせ",
            content="もう見えるはずやわ",
            published_at=timezone.now() - timedelta(days=1),
        )

    def test_notification_visibility(self):
        """ポータル画面での表示テスト"""
        url = reverse("portal:index")
        response = self.client.get(url)

        # 過去の分は表示される、未来の分は表示されない
        self.assertContains(response, self.past_notice.title)
        self.assertNotContains(response, self.future_notice.title)

    def test_detail_view(self):
        """詳細画面のテスト"""
        url = reverse(
            "notification:detail", kwargs={"pk": self.past_notice.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.past_notice.content)


class AdminPermissionTest(TestCase):
    """
    管理画面の権限テスト。
    """

    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="staff@example.com",
            password="password123",
            is_staff=True,
            is_active=True,
        )
        self.normal_user = User.objects.create_user(
            email="normal@example.com",
            password="password123",
            is_staff=False,
            is_active=True,
        )

    def test_staff_can_access_admin(self):
        """スタッフユーザーは管理画面にアクセスできる"""
        self.client.force_login(self.staff_user)
        url = reverse("admin:notification_notification_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_staff_cannot_access_admin(self):
        """一般ユーザーは管理画面にアクセスできない"""
        self.client.force_login(self.normal_user)
        url = reverse("admin:notification_notification_changelist")
        response = self.client.get(url)
        # 権限がない場合、通常はログイン画面へリダイレクト(302)される
        self.assertNotEqual(response.status_code, 200)
