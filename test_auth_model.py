import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_app_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
print("Current User Model:", get_user_model())
