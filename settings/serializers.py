from rest_framework import serializers
from .models import Settings, Notification, AddFeature, Feedback

class SettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Settings
        fields = ['theme', 'language', 'font_size', 'font_family', 'font_color', 'background_color', 'text_color']

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['title', 'library_verse']

class AddFeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = AddFeature
        fields = ['select_category', 'feature_description']

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['feedback_description']


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=True)

    def validate_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Incorrect password.")
        return value
