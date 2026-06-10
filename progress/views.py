from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UserProgress
from .serializers import UserProgressSerializer
from drf_yasg.utils import swagger_auto_schema

class UserProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
        serializer = UserProgressSerializer(user_progress)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=UserProgressSerializer)
    def put(self, request):
        user_progress, _ = UserProgress.objects.get_or_create(user=request.user)
        serializer = UserProgressSerializer(user_progress, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
