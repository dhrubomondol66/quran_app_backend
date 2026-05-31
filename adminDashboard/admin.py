from django.contrib import admin
from .models import Overview, UserManagement, ProfileSettings


@admin.register(Overview)
class OverviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_users', 'total_earn', 'premium_users', 'free_users', 'user_growth', 'revenue')


@admin.register(UserManagement)
class UserManagementAdmin(admin.ModelAdmin):
    list_display = ('user', 'subscription_status', 'actions', 'created_at', 'updated_at')


@admin.register(ProfileSettings)
class ProfileSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'is_admin', 'is_active')