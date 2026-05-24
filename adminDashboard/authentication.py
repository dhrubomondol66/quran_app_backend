from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions

class ActiveUserJWTAuthentication(JWTAuthentication):
    """JWT authentication that ensures the user is active.

    If the user's ``is_active`` flag is False (e.g., admin suspended the account),
    authentication will fail, effectively logging the user out.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is suspended.', code='user_suspended')
        return (user, validated_token)
