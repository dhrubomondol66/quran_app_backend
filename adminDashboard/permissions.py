from rest_framework.permissions import BasePermission

class IsActiveUser(BasePermission):
    """Allow access only for users with is_active=True."""

    def has_permission(self, request, view):
        if not request.user:
            return False
        return request.user.is_active
