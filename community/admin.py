from django.contrib import admin

from .models import (
    CreateCommunity,
    CommunityMembers,
    InviteMembers,
    CommunityPosts,
    LeaderBoard,
)


@admin.register(CreateCommunity)
class CreateCommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at")
    search_fields = ("name", "user__username")


@admin.register(CommunityMembers)
class CommunityMembersAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "created_at")


@admin.register(InviteMembers)
class InviteMembersAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "created_at")


@admin.register(CommunityPosts)
class CommunityPostsAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "created_at")


@admin.register(LeaderBoard)
class LeaderBoardAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "points")
