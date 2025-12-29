# -*- coding: utf-8 -*-
from django.core.management.utils import get_random_secret_key
import secrets

token = secrets.token_urlsafe(4)
secret_key = get_random_secret_key()
print(f'''#
# DEBUG = true
# ALLOWED_HOSTS = ["*"]
# SESSION_COOKIE_NAME = "popon_{token}_sessionid"
# CSRF_COOKIE_NAME = "popon_{token}_csrftoken"
SECRET_KEY = "popon_seckey_{secret_key}"''')
