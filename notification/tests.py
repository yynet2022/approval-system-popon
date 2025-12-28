from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from .models import Notification


class NotificationTest(TestCase):
    """
    お知らせ機能のテスト。
    """
    def setUp(self):
        # 未来のお知らせ
        self.future_notice = Notification.objects.create(
            title="未来のお知らせ",
            content="まだ見えへんはずやで",
            published_at=timezone.now() + timedelta(days=1)
        )
        # 過去のお知らせ
        self.past_notice = Notification.objects.create(
            title="過去のお知らせ",
            content="もう見えるはずやわ",
            published_at=timezone.now() - timedelta(days=1)
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
            "notification:detail",
            kwargs={"pk": self.past_notice.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.past_notice.content)
