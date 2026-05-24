from .models import Subscription


def user_has_active_subscription(user):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_admin", False):
        return True
    try:
        subscription = user.subscription.first()
        if subscription is None:
            return False
        return subscription.is_valid()
    except Subscription.DoesNotExist:
        return False
