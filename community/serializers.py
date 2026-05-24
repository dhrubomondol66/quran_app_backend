from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    CreateCommunity,
    CommunityMembers,
    InviteMembers,
    CommunityPosts,
    LeaderBoard,
)

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "photo"]


class CommunityMemberSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = CommunityMembers
        fields = ["id", "user", "created_at"]


class CommunityListSerializer(serializers.ModelSerializer):
    owner = UserSummarySerializer(source="user", read_only=True)
    member_count = serializers.SerializerMethodField()
    members = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = CreateCommunity
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "member_count",
            "members",
            "is_member",
            "is_owner",
            "created_at",
            "updated_at",
        ]

    def _collect_member_users(self, obj):
        users = []
        seen = set()
        memberships = obj.members.all()
        if hasattr(memberships, "select_related"):
            memberships = memberships.select_related("user")
        for membership in memberships:
            if membership.user_id not in seen:
                users.append(membership.user)
                seen.add(membership.user_id)
        if obj.user_id not in seen:
            users.insert(0, obj.user)
        return users

    def get_members(self, obj):
        return UserSummarySerializer(
            self._collect_member_users(obj),
            many=True,
        ).data

    def get_member_count(self, obj):
        return len(self._collect_member_users(obj))

    def _request_user(self):
        request = self.context.get("request")
        return request.user if request else None

    def get_is_member(self, obj):
        user = self._request_user()
        if not user or not user.is_authenticated:
            return False
        if obj.user_id == user.id:
            return True
        return obj.members.filter(user_id=user.id).exists()

    def get_is_owner(self, obj):
        user = self._request_user()
        return bool(user and user.is_authenticated and obj.user_id == user.id)


class CommunityDetailSerializer(CommunityListSerializer):
    class Meta(CommunityListSerializer.Meta):
        fields = CommunityListSerializer.Meta.fields


class CreateCommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = CreateCommunity
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CommunityMembersSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = CommunityMembers
        fields = ["id", "community", "user", "created_at"]
        read_only_fields = ["id", "user", "created_at"]


class InviteMembersSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = InviteMembers
        fields = ["id", "community", "user", "created_at"]
        read_only_fields = ["id", "created_at"]


class CommunityPostsSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = CommunityPosts
        fields = ["id", "community", "user", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "user", "created_at", "updated_at"]


class LeaderBoardSerializer(serializers.ModelSerializer):
    user = UserSummarySerializer(read_only=True)

    class Meta:
        model = LeaderBoard
        fields = ["id", "user", "community", "points", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
