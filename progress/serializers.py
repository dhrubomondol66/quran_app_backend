from rest_framework import serializers
from .models import UserProgress, Achievement, UserAchievement

class UserProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProgress
        fields = ['id', 'user', 'last_read_surah', 'last_read_verse', 'total_time_spent', 'daily_reading_target', 'reading_streak', 'last_reading_date', 'points']

class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ['id', 'name', 'description', 'icon_name', 'points_bonus']

class UserAchievementSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='achievement.name', read_only=True)
    description = serializers.CharField(source='achievement.description', read_only=True)
    icon_name = serializers.CharField(source='achievement.icon_name', read_only=True)
    points_bonus = serializers.IntegerField(source='achievement.points_bonus', read_only=True)

    class Meta:
        model = UserAchievement
        fields = ['id', 'name', 'description', 'icon_name', 'points_bonus', 'earned_at']

        