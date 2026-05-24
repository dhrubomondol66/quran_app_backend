from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from django.conf import settings
from users.models import User

from rest_framework.exceptions import ValidationError
from django.contrib.auth import authenticate

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'photo']
        extra_kwargs = {'password': {'write_only': True}}

    def validate(self, attrs):
        if User.objects.filter(email=attrs["email"]).exists():
            raise ValidationError("Email already taken.")
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class RegisterSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'confirm_password', 'photo']

    def validate(self, attrs):
        if attrs["email"] == settings.ADMIN_EMAIL:
            raise ValidationError("Email is reserved for admin.")
        if attrs["username"].lower() == 'admin':
            raise ValidationError("Username is reserved for admin.")

            raise ValidationError("Email already taken.")
        if User.objects.filter(username=attrs["username"]).exists():
            raise ValidationError("Username already taken.")
        if attrs["password"] != attrs["confirm_password"]:
            raise ValidationError("Passwords do not match.")
        return attrs

    def create(self, attrs):
        photo = attrs.get('photo', None)
        user = User.objects.create_user(
            username=attrs["username"],
            email=attrs["email"],
            password=attrs["password"],
        )
        if photo:
            user.photo = photo
            user.save()
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        try:
            user_obj = User.objects.get(email=email)
            user = authenticate(username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if not user:
            raise ValidationError('Invalid credentials')
        
        attrs['user'] = user
        return attrs

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()



class ChangePasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise ValidationError('New passwords do not match.')
        return attrs

class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(required=True)


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'photo']