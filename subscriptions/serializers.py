from rest_framework import serializers
from .models import Subscription, PaymentHistory


class SubscriptionSerializer(serializers.ModelSerializer):
    is_valid_subscription = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "plan", "is_active", "auto_renew", "started_at", "expires_at", "is_valid_subscription"]

    def get_is_valid_subscription(self, obj):
        return obj.is_valid()

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

class PaymentHistorySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = PaymentHistory
        fields = ["id", "username", "email", "stripe_invoice_id", "amount", "currency", "status", "plan", "created_at"]
        read_only_fields = ["id", "created_at"]