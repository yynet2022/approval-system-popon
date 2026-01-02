from __future__ import annotations

import uuid

from django.db import models


class BaseModel(models.Model):
    """
    全ての具象モデルの親クラスとして機能し、共通フィールドを提供する抽象モデル。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="作成日時"
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        abstract = True
