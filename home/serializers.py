from rest_framework.serializers import ModelSerializer
from .models import UserProfile, HomeContent

class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['user', 'photo']

class HomeContentSerializer(ModelSerializer):
    class Meta:
        model = HomeContent
        fields = ['user_id', 'daily_streak', 'time_spent', 'community_created', 'community_joined']