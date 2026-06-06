from rest_framework.permissions import BasePermission

from subscriptions.services import user_has_active_subscription


class HasActiveSubscription(BasePermission):
    message = "An active subscription is required."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and user_has_active_subscription(request.user)
        )


class IsCommunityOwner(BasePermission):
    message = "Only the community owner can perform this action."

    def has_permission(self, request, view):
        community = getattr(view, "community", None)
        return community is not None and community.user_id == request.user.id
