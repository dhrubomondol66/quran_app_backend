from rest_framework import serializers
from .models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    is_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Subscription
        fields = ["id", "plan", "is_active", "started_at", "expires_at", "is_valid"]

class CreateSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "is_active", "expires_at"]
        extra_kwargs = {
            "is_active": {"required": False},
            "expires_at": {"required": False},
        }

class ChangeSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["plan", "is_active", "expires_at"]
        extra_kwargs = {
            "is_active": {"required": False},
            "expires_at": {"required": False},
        }