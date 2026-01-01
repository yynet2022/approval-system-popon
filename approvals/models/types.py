#
from django.db import models

from .base import Request


class SimpleRequest(Request):
    """
    簡易承認申請モデル。
    """

    request_prefix = "REQ-S"
    url_slug = "simple"

    content = models.TextField(verbose_name="内容")

    class Meta:
        verbose_name = "簡易承認申請"
        verbose_name_plural = "簡易承認申請"


class LocalBusinessTripRequest(Request):
    """
    近距離出張申請モデル。
    """

    request_prefix = "REQ-L"
    url_slug = "trip"

    trip_date = models.DateField(verbose_name="日程")
    destination = models.CharField(max_length=100, verbose_name="行先")
    note = models.TextField(blank=True, verbose_name="補足事項")

    class Meta:
        verbose_name = "近距離出張申請"
        verbose_name_plural = "近距離出張申請"
