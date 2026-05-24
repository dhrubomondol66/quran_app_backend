from django.db import models
from django.conf import settings
from datetime import timedelta

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    def __str__(self):
        return self.user.username

class HomeContent(models.Model):
    daily_streak = models.IntegerField(default=0)
    time_spent = models.DurationField(default=timedelta(0))
    community_created = models.IntegerField(default=0)
    community_joined = models.IntegerField(default=0)
    user_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='home_content')

    def __str__(self):
        return self.user_id.username
    