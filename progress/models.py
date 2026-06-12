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
    points = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Progress"

class ReadVerse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='read_verses')
    surah = models.ForeignKey(Surah, on_delete=models.CASCADE)
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'verse')

    def __str__(self):
        return f"{self.user.username} read Surah {self.surah.id} Verse {self.verse.verse_number}"

class ReadingLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reading_logs')
    surah = models.ForeignKey(Surah, on_delete=models.SET_NULL, null=True, blank=True)
    verses_count = models.IntegerField(default=0)
    time_spent = models.DurationField(default=timedelta(0))
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} read {self.verses_count} verses on {self.timestamp}"

class UserSurahCompletion(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='surah_completions')
    surah = models.ForeignKey(Surah, on_delete=models.CASCADE)
    completed_at = models.DateTimeField(auto_now_add=True)
    points_awarded = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user', 'surah')

    def __str__(self):
        return f"{self.user.username} completed {self.surah.title}"

class Achievement(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    icon_name = models.CharField(max_length=50, blank=True, null=True)
    points_bonus = models.IntegerField(default=0)

    def __str__(self):
        return self.name

class UserAchievement(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"
