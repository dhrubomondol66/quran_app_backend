from rest_framework import serializers
from .models import Surah, Verse, SavedVerse, Bookmark

class VerseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verse
        fields = [
            'id', 'surah', 'verse_number', 'text', 
            'translation_ur', 'translation_en', 'audio_file', 'pdf_file'
        ]

class SurahSerializer(serializers.ModelSerializer):
    class Meta:
        model = Surah
        fields = [
            'id', 'title', 'description', 'total_verses', 
            'audio_file', 'pdf_file'
        ]

class SurahDetailSerializer(serializers.ModelSerializer):
    verses = VerseSerializer(many=True, read_only=True)

    class Meta:
        model = Surah
        fields = [
            'id', 'title', 'description', 'total_verses', 
            'audio_file', 'pdf_file', 'verses'
        ]

class SavedVerseSerializer(serializers.ModelSerializer):
    verse_details = VerseSerializer(source='verse', read_only=True)

    class Meta:
        model = SavedVerse
        fields = ['id', 'user', 'verse', 'verse_details', 'saved_at', 'notes']
        read_only_fields = ['user']

class BookmarkSerializer(serializers.ModelSerializer):
    verse_details = VerseSerializer(source='verse', read_only=True)

    class Meta:
        model = Bookmark
        fields = ['id', 'user', 'verse', 'verse_details', 'position_offset', 'marked_at']
        read_only_fields = ['user']

class LibraryContentSerializer(serializers.Serializer):
    """
    Read-only serializer that shapes admin_dashboard.LibraryContent
    for user-facing responses.
    """
    id           = serializers.IntegerField()
    title        = serializers.CharField()
    description  = serializers.CharField()
    content_type = serializers.CharField()
    access       = serializers.CharField()
    file_url     = serializers.SerializerMethodField()
    cover_url    = serializers.SerializerMethodField()
    created_at   = serializers.DateTimeField()

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover_image and request:
            return request.build_absolute_uri(obj.cover_image.url)
        return None