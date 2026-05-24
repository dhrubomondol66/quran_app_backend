from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import UserProfile, HomeContent
from .serializers import UserProfileSerializer, HomeContentSerializer

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

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
        serializer = HomeContentSerializer(home_content)
        return Response(serializer.data)

    def put(self, request):
        home_content, _ = HomeContent.objects.get_or_create(user_id=request.user)
        serializer = HomeContentSerializer(home_content, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
