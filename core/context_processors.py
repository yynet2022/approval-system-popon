from django.conf import settings


def common(request):
    """
    全てのテンプレートで利用可能な共通コンテキスト変数を返す。
    """
    return {
        'project_name': getattr(settings, 'PROJECT_NAME', '承認システム'),
    }
