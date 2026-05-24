from django.urls import path

from .views import (
    ListCommunitiesView,
    CommunityDetailView,
    CommunityMembersListView,
    CreateCommunityView,
    JoinCommunityView,
    LeaveCommunityView,
    AcceptInviteView,
    RejectInviteView,
    DeleteCommunityView,
    InviteMembersView,
    RemoveCommunityMemberView,
    CommunityPostsView,
    CommunityAudioView,
    LeaderBoardView,
)

urlpatterns = [
    path("", ListCommunitiesView.as_view()),
    path("<int:pk>/", CommunityDetailView.as_view()),
    path("<int:pk>/members/", CommunityMembersListView.as_view()),
    path("<int:pk>/audio/", CommunityAudioView.as_view()),
    path("create-community/", CreateCommunityView.as_view()),
    path("join-community/", JoinCommunityView.as_view()),
    path("leave-community/", LeaveCommunityView.as_view()),
    path("accept-invite/", AcceptInviteView.as_view()),
    path("reject-invite/", RejectInviteView.as_view()),
    path("delete-community/", DeleteCommunityView.as_view()),
    path("invite-members/", InviteMembersView.as_view()),
    path("remove-community-member/", RemoveCommunityMemberView.as_view()),
    path("community-posts/", CommunityPostsView.as_view()),
    path("leaderboard/", LeaderBoardView.as_view()),
]
