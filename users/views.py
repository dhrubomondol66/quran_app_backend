from django.shortcuts import render
from rest_framework import generics
from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    UserLoginSerializer,
    ForgotPasswordSerializer,
    ChangePasswordSerializer,
    RefreshTokenSerializer,
    UpdateProfileSerializer,
    GoogleLoginSerializer
)
from .email_service import send_password_reset_email
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from drf_yasg.utils import swagger_auto_schema

# Create your views here.
class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]
    queryset = User.objects.all()
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Registration successful',
            'user': UserSerializer(user, context={'request': request}).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)

class UserLoginView(APIView):
    permission_classes = [AllowAny]
    @swagger_auto_schema(request_body=UserLoginSerializer)
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Login successful',
            'user': UserSerializer(user, context={'request': request}).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=RefreshTokenSerializer)
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = serializer.validated_data['refresh_token']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserRefreshTokenView(APIView):
    @swagger_auto_schema(request_body=RefreshTokenSerializer)
    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh_token = serializer.validated_data['refresh_token']
            token = RefreshToken(refresh_token)
            return Response({
                'access': str(token.access_token),
                'refresh': str(token),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({
            'user': UserSerializer(request.user, context={'request': request}).data,
        })

class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @swagger_auto_schema(request_body=UpdateProfileSerializer)
    def post(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Profile updated successfully',
            'user': UserSerializer(request.user, context={'request': request}).data,
        })

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ForgotPasswordSerializer)
    def post(self, request):
        """Send password reset email via EmailJS."""
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            return Response(
                {'message': 'If this email exists, a password reset link has been sent'},
                status=status.HTTP_200_OK
            )
        
        # Generate password reset token
        token = default_token_generator.make_token(user)
        
        # Get frontend URL from request or use default
        frontend_url = request.data.get('frontend_url', 'http://localhost:3000')
        
        # Send email via EmailJS
        email_sent = send_password_reset_email(user, token, frontend_url)
        
        if email_sent:
            return Response({
                'message': 'Password reset email sent successfully',
                'reset_url': f'{frontend_url}/reset-password?email={user.email}&token={token}'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to send password reset email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=ChangePasswordSerializer)
    def post(self, request):

        serializer = ChangePasswordSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = request.user

        # set new password directly
        user.set_password(
            serializer.validated_data['new_password']
        )

        user.save()

        return Response(
            {'message': 'Password changed successfully'},
            status=status.HTTP_200_OK
        )


class GoogleLoginView(APIView):
    """Google OAuth2 login endpoint for mobile apps.
    Receives Google token from app and returns JWT tokens.
    No web redirect - fully in-app authentication.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=GoogleLoginSerializer)
    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        # Generate JWT tokens for the user
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'Google login successful',
            'user': UserSerializer(user, context={'request': request}).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """Reset user password using email and reset token."""
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ChangePasswordSerializer)
    def post(self, request):
        """
        Reset password using token.
        Expected payload:
        {
            "email": "user@example.com",
            "token": "reset_token_from_email",
            "new_password": "newpassword123",
            "confirm_password": "newpassword123"
        }
        """
        email = request.data.get('email')
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not all([email, token, new_password, confirm_password]):
            return Response(
                {'error': 'Email, token, and passwords are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_password != confirm_password:
            return Response(
                {'error': 'Passwords do not match'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verify token validity
        if not default_token_generator.check_token(user, token):
            return Response(
                {'error': 'Invalid or expired reset token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        return Response({
            'message': 'Password reset successfully',
            'user': UserSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)