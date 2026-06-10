from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions

class ActiveUserJWTAuthentication(JWTAuthentication):
    """JWT authentication that ensures the user is active.

    If the user's ``is_active`` flag is False (e.g., admin suspended the account),
    authentication will fail, effectively logging the user out.
    """

    def get_raw_token(self, header):
        parts = header.split()
        if len(parts) == 1:
            token = parts[0]
            try:
                token_str = token.decode('utf-8') if isinstance(token, bytes) else token
                if token_str.startswith('eyJ'):
                    return token
            except Exception:
                pass
        return super().get_raw_token(header)

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if not user.is_active:
            raise exceptions.AuthenticationFailed('User account is suspended.', code='user_suspended')
        return (user, validated_token)

