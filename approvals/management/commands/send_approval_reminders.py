import logging
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from approvals.models import Approver, Request

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Send reminder emails for requests that have been "
        "stalled for more than 24 hours."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be sent without actually sending emails.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # 1. 24時間前の日時を計算
        time_threshold = timezone.now() - timedelta(hours=24)

        # 2. 対象となる申請を抽出
        # updated_at が24時間以上前で、かつ status が PENDING のもの
        stalled_requests = Request.objects.filter(
            status=Request.STATUS_PENDING, updated_at__lte=time_threshold
        ).select_related("applicant")

        if not stalled_requests.exists():
            self.stdout.write("No requests found for reminder.")
            return

        # 3. 承認者ごとにグルーピング
        # { user: [ {'request_obj': req, 'url': url}, ... ] }
        reminders = defaultdict(list)

        # 現在のドメインを取得
        # Siteフレームワークが設定されていない場合は例外を発生させる
        current_site = Site.objects.get_current()
        domain = current_site.domain
        protocol = "https" if settings.SECURE_SSL_REDIRECT else "http"

        count = 0
        for req in stalled_requests:
            # 現在のステップの承認者を取得
            current_approver = (
                req.approvers.filter(
                    order=req.current_step, status=Approver.STATUS_PENDING
                )
                .select_related("user")
                .first()
            )

            if not current_approver:
                logger.warning(
                    f"Request {req.request_number} has no pending approver "
                    f"at step {req.current_step}."
                )
                continue

            user = current_approver.user

            # URL生成
            path = reverse("approvals:detail", args=[req.pk])
            full_url = f"{protocol}://{domain}{path}"

            reminders[user].append({"request_obj": req, "url": full_url})
            count += 1

        self.stdout.write(
            f"Found {count} stalled requests. "
            f"Sending reminders to {len(reminders)} approvers."
        )

        if dry_run:
            self.stdout.write("--- DRY RUN MODE ---")

        # 4. メール送信
        subject = (
            f"[{settings.PROJECT_NAME}] Reminder: Pending approval requests"
        )
        from_email = settings.DEFAULT_FROM_EMAIL

        for user, request_list in reminders.items():
            context = {
                "approver_name": user.get_display_name(),
                "request_list": request_list,
            }
            message = render_to_string("emails/approval_reminder.txt", context)

            if dry_run:
                self.stdout.write(f"Would send email to: {user.email}")
                self.stdout.write(f"Subject: {subject}")
                self.stdout.write("--- Message Body Start ---")
                self.stdout.write(message)
                self.stdout.write("--- Message Body End ---")
                continue

            try:
                send_mail(
                    subject,
                    message,
                    from_email,
                    [user.email],
                    fail_silently=False,
                )
                self.stdout.write(
                    f"Sent reminder to {user.email} "
                    f"({len(request_list)} requests)"
                )
            except Exception as e:
                logger.error(
                    f"Failed to send reminder email to {user.email}: {e}"
                )
                self.stderr.write(f"Error sending to {user.email}: {e}")

        if dry_run:
            self.stdout.write("--- DRY RUN COMPLETED ---")
        else:
            self.stdout.write("Reminder process completed.")
