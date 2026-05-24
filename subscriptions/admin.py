from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "is_active", "started_at", "expires_at")
    list_filter = ("is_active", "plan")
    search_fields = ("user__username", "user__email")
