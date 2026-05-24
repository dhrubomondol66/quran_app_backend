import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_app_backend.settings')
django.setup()

from django.contrib.auth import authenticate
from users.models import User

print("All users:")
for u in User.objects.all():
    print(f"Username: {u.username}, Email: {u.email}, Is Active: {u.is_active}, Password hash: {u.password[:20]}...")

# Try authenticating with username
for u in User.objects.all():
    print(f"Trying authenticate for {u.username}:")
    # Let's test checking password directly
    # Assuming password is "password" or whatever they registered with.
    # Let's check with some common passwords if we don't know, or let's see what happens.
