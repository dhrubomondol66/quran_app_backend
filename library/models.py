from django.db import models
from django.conf import settings

class Surah(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    total_verses = models.IntegerField()
    audio_file = models.FileField(upload_to='surah_audio/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='surah_pdf/', null=True, blank=True)

    def __str__(self):
        return self.title

class Verse(models.Model):
    surah = models.ForeignKey(Surah, on_delete=models.CASCADE, related_name='verses')
    verse_number = models.IntegerField()
    text = models.TextField()
    translation_ur = models.TextField(null=True, blank=True) # Urdu Translation
    translation_en = models.TextField(null=True, blank=True) # English Translation
    audio_file = models.FileField(upload_to='verse_audio/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='verse_pdf/', null=True, blank=True)

    class Meta:
        ordering = ['verse_number']
        unique_together = ('surah', 'verse_number')

    def __str__(self):
        return f"Verse {self.verse_number} - {self.surah.title}"

class SavedVerse(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_verses')
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'verse')

    def __str__(self):
        return f"{self.user.username} saved {self.verse}"

class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    verse = models.ForeignKey(Verse, on_delete=models.CASCADE)
    position_offset = models.IntegerField(default=0) # To store scroll position if needed
    marked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} bookmarked {self.verse}"

class LibraryContentAccess(models.Model):
    """Tracks which users have accessed/downloaded library content."""
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='library_accesses')
    content_id = models.IntegerField()                         # FK to admin_dashboard.LibraryContent
    accessed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_id')

    def __str__(self):
        return f"{self.user.username} accessed content #{self.content_id}"