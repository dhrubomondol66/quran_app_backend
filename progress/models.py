from django.db import models
from django.conf import settings
from datetime import timedelta
from library.models import Surah, Verse

class UserProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='progress')
    last_read_surah = models.ForeignKey(Surah, on_delete=models.SET_NULL, null=True, blank=True)
    last_read_verse = models.ForeignKey(Verse, on_delete=models.SET_NULL, null=True, blank=True)
    total_time_spent = models.DurationField(default=timedelta(0))
    daily_reading_target = models.IntegerField(default=1)
    reading_streak = models.IntegerField(default=0)
    last_reading_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Progress"
