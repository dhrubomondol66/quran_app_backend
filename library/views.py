from rest_framework import generics, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly

from .models import Surah, Verse, SavedVerse, Bookmark, LibraryContentAccess  # ← added LibraryContentAccess
from .serializers import (
    SurahSerializer,
    SurahDetailSerializer,
    VerseSerializer,
    SavedVerseSerializer,
    BookmarkSerializer,
    LibraryContentSerializer,   # ← added
)

class LibraryContentAllView(APIView):
    """
    Returns all admin-uploaded content grouped by type in a single response.
    Premium items are locked for non-premium users.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from adminDashboard.models import LibraryContent

        qs = LibraryContent.objects.all().order_by('-created_at')

        # Serialize everything at once
        serializer = LibraryContentSerializer(qs, many=True, context={'request': request})
        data       = _apply_lock(list(serializer.data), request.user)

        # Group by content_type
        grouped = {
            'pdfs':   [],
            'audios': [],
            'books':  [],
        }

        type_map = {
            'pdf':   'pdfs',
            'audio': 'audios',
            'book':  'books',
        }

        for item in data:
            key = type_map.get(item['content_type'])
            if key:
                grouped[key].append(item)

        return Response({
            'total':  len(data),
            'pdfs':   {'count': len(grouped['pdfs']),   'results': grouped['pdfs']},
            'audios': {'count': len(grouped['audios']), 'results': grouped['audios']},
            'books':  {'count': len(grouped['books']),  'results': grouped['books']},
        })

class SurahListView(generics.ListAPIView):
    queryset           = Surah.objects.all()
    serializer_class   = SurahSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class SurahDetailView(generics.RetrieveAPIView):
    queryset           = Surah.objects.all()
    serializer_class   = SurahDetailSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]


class VerseListView(generics.ListAPIView):
    queryset           = Verse.objects.all()
    serializer_class   = VerseSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        qs       = super().get_queryset()
        surah_id = self.request.query_params.get('surah')
        if surah_id:
            qs = qs.filter(surah_id=surah_id)
        return qs


class SavedVerseViewSet(viewsets.ModelViewSet):
    serializer_class   = SavedVerseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or user.is_anonymous:
            return SavedVerse.objects.none()
        return SavedVerse.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class BookmarkViewSet(viewsets.ModelViewSet):
    serializer_class   = BookmarkSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user or user.is_anonymous:
            return Bookmark.objects.none()
        return Bookmark.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ── Admin Library Content (user-facing) ───────────────────────────────────────

def _user_is_premium(user):
    """Shared helper — avoids repeating across all three views."""
    sub = user.subscription.first()
    return sub is not None and sub.is_valid()


def _apply_lock(data, user):
    """Mutates serializer data list — blocks file_url for non-premium users."""
    is_premium = _user_is_premium(user)
    for item in data:
        if item['access'] == 'premium' and not is_premium:
            item['file_url'] = None
            item['locked']   = True
            item['message']  = 'Subscribe to access this content.'
        else:
            item['locked'] = False
    return data


class LibraryContentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from adminDashboard.models import LibraryContent

        qs = LibraryContent.objects.all().order_by('-created_at')

        content_type = request.query_params.get('type')
        access       = request.query_params.get('access')

        if content_type:
            qs = qs.filter(content_type=content_type)
        if access:
            qs = qs.filter(access=access)

        serializer = LibraryContentSerializer(qs, many=True, context={'request': request})
        data       = _apply_lock(list(serializer.data), request.user)
        return Response(data)


class LibraryContentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from adminDashboard.models import LibraryContent

        try:
            content = LibraryContent.objects.get(pk=pk)
        except LibraryContent.DoesNotExist:
            return Response({'error': 'Content not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LibraryContentSerializer(content, context={'request': request})
        data = serializer.data

        if content.access == 'premium' and not _user_is_premium(request.user):
            data['file_url'] = None
            data['locked'] = True
            data['message'] = 'Subscribe to access this content.'
            return Response(data, status=status.HTTP_403_FORBIDDEN)

        LibraryContentAccess.objects.get_or_create(
            user=request.user,
            content_id=content.id,
        )

        return Response({**data, 'locked': False})


class LibraryContentByTypeView(APIView):
    permission_classes = [IsAuthenticated]

    TYPE_MAP = {
        'pdfs':   'pdf',
        'audios': 'audio',
        'books':  'book',
    }

    def get(self, request, content_type):
        from adminDashboard.models import LibraryContent

        mapped = self.TYPE_MAP.get(content_type)
        if not mapped:
            return Response({'error': 'Invalid content type. Use: pdfs, audios, books.'}, status=status.HTTP_400_BAD_REQUEST)

        qs         = LibraryContent.objects.filter(content_type=mapped).order_by('-created_at')
        serializer = LibraryContentSerializer(qs, many=True, context={'request': request})
        data       = _apply_lock(list(serializer.data), request.user)
        return Response(data)