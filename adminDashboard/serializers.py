from rest_framework import serializers
from .models import Overview, SubscriptionPlan, UserManagement, ProfileSettings, LibraryContent
from users.models import User

class OverviewSerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    total_earn = serializers.IntegerField()
    premium_users = serializers.IntegerField()
    free_users = serializers.IntegerField()
    user_growth = serializers.FloatField()  
    revenue = serializers.IntegerField()
    
    class Meta:
        model = Overview
        fields = []


class UserManagementSerializer(serializers.ModelSerializer):
    name         = serializers.CharField(source='user.username', read_only=True)
    email        = serializers.EmailField(source='user.email', read_only=True)
    password     = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    is_active    = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined  = serializers.DateTimeField(source='user.date_joined', read_only=True)

    class Meta:
        model  = UserManagement
        fields = [
            'id', 'name', 'email', 'password', 'is_active', 'date_joined',
            'subscription_status',
            'actions',
            'created_at', 'updated_at',
        ]

class ProfileSettingsSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = ProfileSettings
        fields = ['email', 'password']

    def update(self, instance, validated_data):
        user = instance.user

        # update email
        email = validated_data.get('email')
        if email:
            user.email = email
            instance.email = email

        # update password
        password = validated_data.get('password')
        if password:
            user.set_password(password)

        user.save()
        instance.save()

        return instance
    
class LibraryContentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    file_url         = serializers.SerializerMethodField()
    cover_url        = serializers.SerializerMethodField()

    class Meta:
        model  = LibraryContent
        fields = [
            'id', 'title', 'description', 'content_type', 'access',
            'file', 'file_url', 'cover_image', 'cover_url',
            'uploaded_by_name', 'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'file':        {'write_only': True},   # upload only; read via file_url
            'cover_image': {'write_only': True},
        }

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        return None


# ── Subscription Pricing ──────────────────────────────────────────────────────

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source='updated_by.username', read_only=True)

    class Meta:
        model  = SubscriptionPlan
        fields = [
            'id', 'interval', 'price', 'stripe_price_id',
            'is_active', 'updated_by_name', 'updated_at',
        ]
        read_only_fields = ['stripe_price_id', 'updated_at', 'updated_by_name']