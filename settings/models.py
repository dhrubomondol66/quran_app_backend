from django.db import models
from django.conf import settings
from library.models import Verse

class Settings(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='settings')
    theme = models.CharField(max_length=100, default='light')
    language = models.CharField(max_length=100, default='en')
    font_size = models.IntegerField(default=16)
    font_family = models.CharField(max_length=100, default='Arial')
    font_color = models.CharField(max_length=100, default='#000000')
    background_color = models.CharField(max_length=100, default='#FFFFFF')
    text_color = models.CharField(max_length=100, default='#000000')

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    library_verse = models.ForeignKey(Verse, on_delete=models.CASCADE, related_name='notifications')

class AddFeature(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='add_features')
    select_category = models.CharField(max_length=100, choices=[('reading', 'Reading'), ('audio', 'Audio'), ('translation', 'Translation'), ('interface', 'Interface'), ('progress', 'Progress'), ('other', 'Other')])
    feature_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} added {self.select_category} feature"

class Feedback(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedbacks')
    feedback_description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class UserProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_profile')
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class UserSettings(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_settings')
    theme = models.CharField(max_length=100, default='light')
    language = models.CharField(max_length=100, default='en')
    font_size = models.IntegerField(default=16)
    font_family = models.CharField(max_length=100, default='Arial')
    font_color = models.CharField(max_length=100, default='#000000')
    background_color = models.CharField(max_length=100, default='#FFFFFF')
    text_color = models.CharField(max_length=100, default='#000000')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self):  
        return f"{self.user.username}'s Settings"