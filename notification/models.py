from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Notification(BaseModel):
    """
    システムからユーザーへのお知らせ。
    """
    title = models.CharField(
        max_length=255,
        verbose_name="タイトル"
    )
    content = models.TextField(
        verbose_name="本文"
    )
    published_at = models.DateTimeField(
        default=timezone.now,
        verbose_name="公開日時"
    )

    def __str__(self):
        return self.title
