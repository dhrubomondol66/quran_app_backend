from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .models import Settings, Notification, AddFeature, Feedback, FCMDevice, AppRating
from .serializers import (
    SettingsSerializer,
    NotificationSerializer,
    AddFeatureSerializer,
    FeedbackSerializer,
    DeleteAccountSerializer,
    FCMDeviceSerializer,
    AppRatingSerializer,
)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class SettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings_obj, _ = Settings.objects.get_or_create(user=request.user)
        serializer = SettingsSerializer(settings_obj)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=SettingsSerializer)
    def put(self, request):
        settings_obj, _ = Settings.objects.get_or_create(user=request.user)
        serializer = SettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=NotificationSerializer)
    def post(self, request):
        serializer = NotificationSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        """Mark all notifications as read."""
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'message': 'All notifications marked as read.'}, status=status.HTTP_200_OK)

class AddFeatureView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        add_features = AddFeature.objects.filter(user=request.user)
        serializer = AddFeatureSerializer(add_features, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=AddFeatureSerializer)
    def post(self, request):
        serializer = AddFeatureSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        feedbacks = Feedback.objects.filter(user=request.user)
        serializer = FeedbackSerializer(feedbacks, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=FeedbackSerializer)
    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteAccountView(APIView):
    """Permanently delete the authenticated user's account."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=DeleteAccountSerializer)
    def delete(self, request):
        serializer = DeleteAccountSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = request.user
        # Cancel any active subscription on Stripe
        try:
            subscription = user.subscription.first()
            if subscription and subscription.stripe_subscription_id:
                import stripe
                from django.conf import settings
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe.Subscription.delete(subscription.stripe_subscription_id)
        except Exception as e:
            print(f"Failed to cancel Stripe subscription during account deletion: {e}")

        user.delete()
        return Response(
            {"message": "Your account has been deleted successfully."},
            status=status.HTTP_200_OK,
        )

    @swagger_auto_schema(request_body=DeleteAccountSerializer)
    def post(self, request):
        """Alias for clients that cannot send DELETE with a body."""
        return self.delete(request)


class FCMDeviceRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(request_body=FCMDeviceSerializer)
    def post(self, request):
        serializer = FCMDeviceSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        token = serializer.validated_data['token']
        device, created = FCMDevice.objects.get_or_create(
            token=token,
            defaults={'user': request.user}
        )
        if not created and device.user != request.user:
            device.user = request.user
            device.save()

        return Response(FCMDeviceSerializer(device).data, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description="The FCM token to unregister"),
            }
        )
    )
    def delete(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        deleted, _ = FCMDevice.objects.filter(user=request.user, token=token).delete()
        if deleted:
            return Response({'message': 'Device unregistered successfully.'}, status=status.HTTP_200_OK)
        return Response({'error': 'Device token not found for this user.'}, status=status.HTTP_404_NOT_FOUND)

class AppRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ratings = AppRating.objects.filter(user=request.user)
        serializer = AppRatingSerializer(ratings, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=AppRatingSerializer)
    def post(self, request):
        serializer = AppRatingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)