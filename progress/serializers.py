from rest_framework import serializers
from .models import UserProgress

class UserProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProgress
        fields = ['id', 'user', 'last_read_surah', 'last_read_verse', 'total_time_spent', 'daily_reading_target', 'reading_streak', 'last_reading_date']

        