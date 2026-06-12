from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from library.models import Surah, Verse
from library.serializers import SurahSerializer, VerseSerializer
from subscriptions.services import user_has_active_subscription

from .models import CreateCommunity, CommunityMembers, InviteMembers, CommunityPosts, LeaderBoard, JoinRequest
from .permissions import HasActiveSubscription
from .serializers import (
    CommunityListSerializer,
    CommunityDetailSerializer,
    CreateCommunitySerializer,
    CommunityMemberSerializer,
    CommunityMembersSerializer,
    InviteMembersSerializer,
    CommunityPostsSerializer,
    LeaderBoardSerializer,
    JoinRequestSerializer,
)


def _community_queryset():
    return CreateCommunity.objects.select_related("user").prefetch_related(
        Prefetch(
            "members",
            queryset=CommunityMembers.objects.select_related("user"),
        )
    )


def _user_is_member(community, user):
    if community.user_id == user.id:
        return True
    return CommunityMembers.objects.filter(community=community, user=user).exists()


def _require_member(community, user):
    if not _user_is_member(community, user):
        raise PermissionDenied("Join this community to access its content.")


def _require_owner(community, user):
    if community.user_id != user.id:
        raise PermissionDenied("Only the community owner can perform this action.")


class ListCommunitiesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        communities = _community_queryset()
        serializer = CommunityListSerializer(
            communities,
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "can_create_community": user_has_active_subscription(request.user),
                "communities": serializer.data,
            }
        )


class CommunityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        community = get_object_or_404(_community_queryset(), pk=pk)
        serializer = CommunityDetailSerializer(community, context={"request": request})
        return Response(serializer.data)


class CommunityMembersListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        community = get_object_or_404(CreateCommunity, pk=pk)
        memberships = CommunityMembers.objects.filter(community=community).select_related("user")
        serializer = CommunityMemberSerializer(memberships, many=True)
        owner = community.user
        return Response(
            {
                "owner": {
                    "id": owner.id,
                    "username": owner.username,
                    "email": owner.email,
                    "photo": owner.photo.url if owner.photo else None,
                },
                "members": serializer.data,
            }
        )


class CreateCommunityView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    @swagger_auto_schema(request_body=CreateCommunitySerializer)
    def post(self, request):
        serializer = CreateCommunitySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        community = serializer.save(user=request.user)
        CommunityMembers.objects.get_or_create(community=community, user=request.user)
        
        # Send push notification to all other active users
        try:
            from django.contrib.auth import get_user_model
            from settings.notifications import send_push_notification
            User = get_user_model()
            all_users = User.objects.filter(is_active=True).exclude(id=request.user.id)
            send_push_notification(
                user_or_users=all_users,
                title="New Community Created",
                body=f"Explore the new community '{community.name}' created by {request.user.username}!",
                notification_type='community_created',
                extra_data={'community_id': community.id}
            )
        except Exception as e:
            print(f"Failed to send community creation notification: {e}")

        community = _community_queryset().get(pk=community.pk)
        return Response(
            CommunityDetailSerializer(community, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class JoinCommunityView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['community'],
            properties={
                'community': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the community to join'),
            }
        )
    )
    def post(self, request):
        community_id = request.data.get("community")
        if not community_id:
            raise ValidationError({"community": "This field is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        
        # Check if already a member
        if _user_is_member(community, request.user):
            return Response(
                {"message": "You are already a member of this community."},
                status=status.HTTP_200_OK,
            )

        # Create join request
        join_request, created = JoinRequest.objects.get_or_create(
            community=community,
            user=request.user,
            defaults={"status": "pending"}
        )
        
        if not created:
            if join_request.status == 'pending':
                return Response(
                    {
                        "message": "You have already submitted a join request. Status: pending.",
                        "join_request": JoinRequestSerializer(join_request).data
                    },
                    status=status.HTTP_200_OK
                )
            else:
                join_request.status = 'pending'
                join_request.save()

        # Send push notification to the community owner (admin of the community)
        try:
            from settings.notifications import send_push_notification
            send_push_notification(
                user_or_users=community.user,
                title="New Join Request",
                body=f"{request.user.username} has requested to join your community '{community.name}'.",
                notification_type='join_request',
                extra_data={'community_id': community.id, 'join_request_id': join_request.id}
            )
        except Exception as e:
            print(f"Failed to send join request notification: {e}")

        return Response(
            {
                "message": "Join request submitted successfully.",
                "join_request": JoinRequestSerializer(join_request).data
            },
            status=status.HTTP_201_CREATED,
        )


class ListJoinRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        community_id = request.query_params.get("community")
        if community_id:
            community = get_object_or_404(CreateCommunity, pk=community_id)
            _require_owner(community, request.user)
            requests = JoinRequest.objects.filter(community=community, status='pending').select_related("user", "community")
        else:
            requests = JoinRequest.objects.filter(community__user=request.user, status='pending').select_related("user", "community")
        
        serializer = JoinRequestSerializer(requests, many=True)
        return Response(serializer.data)


class RespondJoinRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['action'],
            properties={
                'action': openapi.Schema(type=openapi.TYPE_STRING, description="Choose 'approve' or 'decline'"),
            }
        )
    )
    def post(self, request, pk):
        join_request = get_object_or_404(JoinRequest, pk=pk)
        _require_owner(join_request.community, request.user)

        action = request.data.get("action")
        if action not in ['approve', 'decline']:
            raise ValidationError({"action": "Choose 'approve' or 'decline'."})

        if action == 'approve':
            join_request.status = 'approved'
            join_request.save()

            membership, _ = CommunityMembers.objects.get_or_create(
                community=join_request.community,
                user=join_request.user
            )

            # Send push notification to requester
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=join_request.user,
                    title="Join Request Approved",
                    body=f"Your request to join the community '{join_request.community.name}' has been approved!",
                    notification_type='join_response',
                    extra_data={'community_id': join_request.community.id, 'status': 'approved'}
                )
            except Exception as e:
                print(f"Failed to send join approval notification: {e}")

            return Response(
                {
                    "message": "Join request approved.",
                    "membership": CommunityMembersSerializer(membership).data
                },
                status=status.HTTP_200_OK
            )
        else:
            join_request.status = 'declined'
            join_request.save()

            # Send push notification to requester
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=join_request.user,
                    title="Join Request Declined",
                    body=f"Your request to join the community '{join_request.community.name}' has been declined.",
                    notification_type='join_response',
                    extra_data={'community_id': join_request.community.id, 'status': 'declined'}
                )
            except Exception as e:
                print(f"Failed to send join decline notification: {e}")

            return Response({"message": "Join request declined."}, status=status.HTTP_200_OK)


class LeaveCommunityView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['community'],
            properties={
                'community': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the community to leave'),
            }
        )
    )
    def post(self, request):
        community_id = request.data.get("community")
        if not community_id:
            raise ValidationError({"community": "This field is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        if community.user_id == request.user.id:
            raise PermissionDenied(
                "Community owners cannot leave. Delete the community instead."
            )
        deleted, _ = CommunityMembers.objects.filter(
            community=community,
            user=request.user,
        ).delete()
        if not deleted:
            raise NotFound("You are not a member of this community.")
        return Response({"message": "Left community successfully"})


class DeleteCommunityView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['community'],
            properties={
                'community': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the community to delete'),
            }
        )
    )
    def post(self, request):
        community_id = request.data.get("community")
        if not community_id:
            raise ValidationError({"community": "This field is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_owner(community, request.user)
        community.delete()
        return Response({"message": "Community deleted successfully"})


class InviteMembersView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['community', 'user'],
            properties={
                'community': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the community'),
                'user': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the user to invite'),
            }
        )
    )
    def post(self, request):
        community_id = request.data.get("community")
        user_id = request.data.get("user")
        if not community_id or not user_id:
            raise ValidationError(
                {"detail": "Both 'community' and 'user' are required."}
            )
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_owner(community, request.user)
        if CommunityMembers.objects.filter(community=community, user_id=user_id).exists():
            raise ValidationError({"user": "User is already a member."})
        invite, created = InviteMembers.objects.get_or_create(
            community=community,
            user_id=user_id,
        )
        if not created:
            return Response(
                {"message": "User already invited."},
                status=status.HTTP_200_OK,
            )
        return Response(
            InviteMembersSerializer(invite).data,
            status=status.HTTP_201_CREATED,
        )


class AcceptInviteView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['invite'],
            properties={
                'invite': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the invite to accept'),
            }
        )
    )
    def post(self, request):
        invite_id = request.data.get("invite")
        if not invite_id:
            raise ValidationError({"invite": "This field is required."})
        invite = get_object_or_404(InviteMembers, pk=invite_id, user=request.user)
        membership, _ = CommunityMembers.objects.get_or_create(
            community=invite.community,
            user=request.user,
        )
        invite.delete()
        return Response(CommunityMembersSerializer(membership).data)


class RejectInviteView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['invite'],
            properties={
                'invite': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the invite to reject'),
            }
        )
    )
    def post(self, request):
        invite_id = request.data.get("invite")
        if not invite_id:
            raise ValidationError({"invite": "This field is required."})
        invite = get_object_or_404(InviteMembers, pk=invite_id, user=request.user)
        invite.delete()
        return Response({"message": "Rejected invite successfully"})


class RemoveCommunityMemberView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['community', 'user'],
            properties={
                'community': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the community'),
                'user': openapi.Schema(type=openapi.TYPE_INTEGER, description='ID of the user to remove'),
            }
        )
    )
    def post(self, request):
        community_id = request.data.get("community")
        user_id = request.data.get("user")
        if not community_id or not user_id:
            raise ValidationError(
                {"detail": "Both 'community' and 'user' are required."}
            )
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_owner(community, request.user)
        if int(user_id) == request.user.id:
            raise ValidationError({"user": "Owner cannot remove themselves."})
        deleted, _ = CommunityMembers.objects.filter(
            community=community,
            user_id=user_id,
        ).delete()
        if not deleted:
            raise NotFound("Member not found in this community.")
        return Response({"message": "Removed member successfully"})


class CommunityPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        community_id = request.query_params.get("community")
        if not community_id:
            raise ValidationError({"community": "Query param 'community' is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_member(community, request.user)
        posts = (
            CommunityPosts.objects.filter(community=community)
            .select_related("user")
            .order_by("-created_at")
        )
        return Response(CommunityPostsSerializer(posts, many=True).data)

    @swagger_auto_schema(request_body=CommunityPostsSerializer)
    def post(self, request):
        community_id = request.data.get("community")
        if not community_id:
            raise ValidationError({"community": "This field is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_member(community, request.user)
        serializer = CommunityPostsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(user=request.user, community=community)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CommunityAudioView(APIView):
    """Quran audio from the library — available to community members."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        community = get_object_or_404(CreateCommunity, pk=pk)
        _require_member(community, request.user)
        surahs = Surah.objects.exclude(audio_file="").exclude(audio_file__isnull=True)
        surah_id = request.query_params.get("surah")
        if surah_id:
            verses = Verse.objects.filter(surah_id=surah_id).exclude(
                audio_file=""
            ).exclude(audio_file__isnull=True)
            return Response(
                {
                    "surah": SurahSerializer(
                        get_object_or_404(Surah, pk=surah_id)
                    ).data,
                    "verses": VerseSerializer(verses, many=True).data,
                }
            )
        return Response({"surahs": SurahSerializer(surahs, many=True).data})


class LeaderBoardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        community_id = request.query_params.get("community")
        if not community_id:
            raise ValidationError({"community": "Query param 'community' is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_member(community, request.user)

        # Sync LeaderBoard entries for all members
        memberships = CommunityMembers.objects.filter(community=community).select_related("user")
        from progress.models import UserProgress
        for member in memberships:
            up, _ = UserProgress.objects.get_or_create(user=member.user)
            lb_entry, _ = LeaderBoard.objects.get_or_create(
                user=member.user,
                community=community,
            )
            if lb_entry.points != up.points:
                lb_entry.points = up.points
                lb_entry.save(update_fields=['points'])

        # Sync community owner/creator too
        owner = community.user
        up, _ = UserProgress.objects.get_or_create(user=owner)
        lb_entry, _ = LeaderBoard.objects.get_or_create(
            user=owner,
            community=community,
        )
        if lb_entry.points != up.points:
            lb_entry.points = up.points
            lb_entry.save(update_fields=['points'])

        entries = LeaderBoard.objects.filter(community=community).select_related(
            "user"
        ).order_by("-points")
        return Response(LeaderBoardSerializer(entries, many=True).data)

    @swagger_auto_schema(request_body=LeaderBoardSerializer)
    def post(self, request):
        community_id = request.data.get("community")
        if not community_id:
            raise ValidationError({"community": "This field is required."})
        community = get_object_or_404(CreateCommunity, pk=community_id)
        _require_member(community, request.user)
        serializer = LeaderBoardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(user=request.user, community=community)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
