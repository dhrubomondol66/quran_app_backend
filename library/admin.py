from django.contrib import admin
from .models import Surah, Verse, SavedVerse, Bookmark

@admin.register(Surah)
class SurahAdmin(admin.ModelAdmin):
    list_display = ('title', 'total_verses', 'audio_file', 'pdf_file')
    search_fields = ('title',)

@admin.register(Verse)
class VerseAdmin(admin.ModelAdmin):
    list_display = ('surah', 'verse_number', 'text', 'audio_file', 'pdf_file')
    list_filter = ('surah',)
    search_fields = ('text', 'translation_ur', 'translation_en')

@admin.register(SavedVerse)
class SavedVerseAdmin(admin.ModelAdmin):
    list_display = ('user', 'verse', 'saved_at')
    list_filter = ('user',)

@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ('user', 'verse', 'marked_at')
    list_filter = ('user',)
