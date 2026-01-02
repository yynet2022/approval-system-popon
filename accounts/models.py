from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class UserManager(BaseUserManager["User"]):
    """
    カスタムユーザーマネージャー。
    メールアドレスを主識別子として使用する。
    """

    def create_user(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> User:
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    カスタムユーザーモデル。
    """

    email = models.EmailField(
        unique=True, blank=False, null=False, verbose_name="メールアドレス"
    )
    last_name = models.CharField(max_length=150, blank=True, verbose_name="姓")
    first_name = models.CharField(
        max_length=150, blank=True, verbose_name="名"
    )
    is_staff = models.BooleanField(
        default=False, verbose_name="管理サイトアクセス権限"
    )
    is_active = models.BooleanField(default=False, verbose_name="有効フラグ")
    is_approver = models.BooleanField(
        default=False, verbose_name="承認者候補フラグ"
    )
    date_joined = models.DateTimeField(
        default=timezone.now, verbose_name="登録日時"
    )

    objects: UserManager = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def get_full_name(self) -> str:
        """
        姓と名を半角スペースで結合して返す。
        """
        return f"{self.last_name} {self.first_name}".strip()

    def get_display_name(self) -> str:
        """
        フルネームがあればそれを返し、なければメールアドレスを返す。
        """
        return self.get_full_name() or self.email

    def __str__(self) -> str:
        return self.get_display_name()


class LoginToken(BaseModel):
    """
    マジックリンク認証用の一時トークン。
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()

    @classmethod
    def create_token(cls, user: User) -> LoginToken:
        """
        新しいトークンを生成して保存する。
        """
        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(minutes=30)
        return cls.objects.create(
            user=user, token=token, expires_at=expires_at
        )
