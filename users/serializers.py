from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from django.conf import settings
from users.models import User

from rest_framework.exceptions import ValidationError
from django.contrib.auth import authenticate

class UserSerializer(serializers.ModelSerializer):
    photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'photo']
        extra_kwargs = {'password': {'write_only': True}}

    def get_photo(self, obj):
        request = self.context.get('request')
        if obj.photo:
            if request:
                return request.build_absolute_uri(obj.photo.url)
            return obj.photo.url
        return None

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
    photo = serializers.ImageField(required=True)

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

        if not user.is_active:
            raise ValidationError('Your account has been suspended. Please contact support.')

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
        fields = ['username', 'photo']



class GoogleLoginSerializer(serializers.Serializer):
    """Serializer for Google OAuth2 login - receives token from mobile app."""
    id_token = serializers.CharField(required=False, allow_blank=True)
    google_id = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=False, allow_blank=True)
    photo_url = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        """Validate Google login data and get or create user."""
        id_token = attrs.get('id_token')
        google_id = attrs.get('google_id')
        email = attrs.get('email')
        name = attrs.get('name', '')
        photo_url = attrs.get('photo_url', '')

        # Securely verify the ID token if provided
        if id_token:
            decoded_token = None
            
            # 1. Try Firebase Admin SDK verification (if it's a Firebase ID token)
            try:
                from settings.firebase_init import initialize_firebase
                initialize_firebase()
                from firebase_admin import auth
                decoded_token = auth.verify_id_token(id_token)
                
                # Retrieve verified details
                email = decoded_token.get('email') or email
                google_id = decoded_token.get('uid') or google_id
                name = decoded_token.get('name') or name
                photo_url = decoded_token.get('picture') or photo_url
                
            except Exception as firebase_err:
                # 2. Try Google OAuth tokeninfo verification (if standard Google ID token)
                import requests
                try:
                    response = requests.get(
                        f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}",
                        timeout=10
                    )
                    if response.status_code == 200:
                        google_payload = response.json()
                        email = google_payload.get('email') or email
                        google_id = google_payload.get('sub') or google_id
                        name = google_payload.get('name') or name
                        photo_url = google_payload.get('picture') or photo_url
                    else:
                        raise ValidationError("Invalid Firebase or Google ID Token.")
                except Exception as google_err:
                    raise ValidationError(f"ID Token verification failed: {str(firebase_err)} / {str(google_err)}")

        if not email or not google_id:
            raise ValidationError("Email and Google ID are required to complete sign-in.")

        # Try to get user by google_id first, then by email
        user = User.objects.filter(google_id=google_id).first()
        if not user:
            user = User.objects.filter(email=email).first()
        
        # Create user if doesn't exist
        if not user:
            # Generate unique username from email
            base_username = email.split('@')[0] if email else 'google_user'
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=None,  # No password for OAuth users
            )
        
        # Update Google ID if not already set
        if not user.google_id:
            user.google_id = google_id
            user.save()
        
        # Update user info if provided
        if name and not user.username:
            user.username = name.split()[0] if name else user.username
            user.save()

        # Securely download and store user photo locally if not already set
        if photo_url and not user.photo:
            try:
                import requests
                from django.core.files.base import ContentFile
                img_resp = requests.get(photo_url, timeout=10)
                if img_resp.status_code == 200:
                    user.photo.save(f"google_{user.id}.jpg", ContentFile(img_resp.content), save=True)
            except Exception as e:
                print(f"Failed to download Google profile photo: {e}")
        
        attrs['user'] = user
        return attrs