from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.conf import settings
from users.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
# Create your models here.

class Overview(models.Model):
    """Kept minimal — real counts are computed live in the view."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='overview')
    total_users= models.IntegerField(default=0)
    total_earn= models.IntegerField(default=0)
    premium_users= models.IntegerField(default=0)
    free_users= models.IntegerField(default=0)
    user_growth= models.IntegerField(default=0)
    revenue= models.IntegerField(default=0)

    def __str__(self):
        return f"Overview for {self.user.username}"

class UserManagement(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_activity')
    subscription_status = models.CharField(max_length=100, default='free', blank=True)
    actions = models.CharField(max_length=100, choices=[('active', 'Active'), ('suspend', 'Suspend'), ('delete', 'Delete')], default='active', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if self.actions == 'active':
            self.user.is_active = True
            self.user.save()
        elif self.actions == 'suspend':
            self.user.is_active = False
            self.user.save()
        elif self.actions == 'delete':
            self.user.delete()
            return  # prevent saving after delete
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.user.username}'s User Management"

class ProfileSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile_settings')
    # Admin identity fields
    email = models.EmailField(default='', blank=True)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if self.email:
            self.user.email = self.email
        if self.is_admin:
            self.user.is_admin = True
        self.user.is_active = self.is_active
        self.user.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username}'s Profile Settings"
    
class LibraryContent(models.Model):
    class ContentType(models.TextChoices):
        PDF   = 'pdf',   'PDF'
        AUDIO = 'audio', 'Audio'
        BOOK  = 'book',  'Book'

    class AccessType(models.TextChoices):
        FREE    = 'free',    'Free'
        PREMIUM = 'premium', 'Premium'

    title        = models.CharField(max_length=255)
    description  = models.TextField(blank=True)
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    access       = models.CharField(max_length=20, choices=AccessType.choices, default=AccessType.FREE)
    file         = models.FileField(upload_to='library/%Y/%m/')   # PDF / audio / book file
    cover_image  = models.ImageField(upload_to='library/covers/', blank=True, null=True)
    uploaded_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='library_uploads')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.content_type.upper()}] {self.title}"


# ── Subscription Pricing (admin-controlled) ───────────────────────────────────

class SubscriptionPlan(models.Model):
    class Interval(models.TextChoices):
        MONTHLY = 'monthly', 'Monthly'
        YEARLY  = 'yearly',  'Yearly'

    interval          = models.CharField(max_length=20, choices=Interval.choices, unique=True)
    price             = models.DecimalField(max_digits=8, decimal_places=2)   # e.g. 9.99
    stripe_price_id   = models.CharField(max_length=100, blank=True)          # synced to Stripe
    is_active         = models.BooleanField(default=True)
    updated_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at        = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.interval} — ${self.price}"

@receiver(post_save, sender=User)
def create_user_management(sender, instance, created, **kwargs):
    """Create a UserManagement entry for each new non‑admin user.
    This ensures the admin dashboard always has a record to display.
    """
    if created and not instance.is_admin:
        UserManagement.objects.get_or_create(user=instance)
