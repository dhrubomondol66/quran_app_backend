from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SurahListView,
    SurahDetailView,
    VerseListView,
    SavedVerseViewSet,
    BookmarkViewSet,
    LibraryContentAllView,
)

router = DefaultRouter()
router.register('saved-verses', SavedVerseViewSet, basename='saved-verses')
router.register('bookmarks', BookmarkViewSet, basename='bookmarks')

urlpatterns = [
    path('surahs/', SurahListView.as_view(), name='surah-list'),
    path('surahs/<int:pk>/', SurahDetailView.as_view(), name='surah-detail'),
    path('verses/', VerseListView.as_view(), name='verse-list'),
    path('list-library/', LibraryContentAllView.as_view(), name='list-library-all'),
    path('', include(router.urls)),
]
