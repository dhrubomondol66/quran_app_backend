from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile, HomeContent
from .serializers import UserProfileSerializer, HomeContentSerializer
from drf_yasg.utils import swagger_auto_schema

from progress.models import UserProgress, ReadingLog
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=UserProfileSerializer)
    def put(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

class HomeContentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        home_content, _ = HomeContent.objects.get_or_create(user_id=request.user)
        try:
            progress, _ = UserProgress.objects.get_or_create(user=request.user)
            home_content.daily_streak = progress.reading_streak
            
            today = timezone.localtime(timezone.now()).date()
            today_logs = ReadingLog.objects.filter(user=request.user, timestamp__date=today)
            total_duration = today_logs.aggregate(total=Sum('time_spent'))['total'] or timedelta(0)
            home_content.time_spent = total_duration
            
            from community.models import CreateCommunity, CommunityMembers
            home_content.community_created = CreateCommunity.objects.filter(user=request.user).count()
            home_content.community_joined = CommunityMembers.objects.filter(user=request.user).count()
            home_content.save()
        except Exception as e:
            print("Error syncing HomeContent: ", e)

        serializer = HomeContentSerializer(home_content)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=HomeContentSerializer)
    def put(self, request):
        home_content, _ = HomeContent.objects.get_or_create(user_id=request.user)
        serializer = HomeContentSerializer(home_content, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
