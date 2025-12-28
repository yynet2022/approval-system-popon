from django.views.generic import DetailView

from .models import Notification


class NotificationDetailView(DetailView):
    """
    お知らせ詳細画面。
    """
    model = Notification
    template_name = "notification/detail.html"
    context_object_name = "notification"
