import logging
from settings.models import Notification, FCMDevice
from django.conf import settings

logger = logging.getLogger(__name__)

def send_push_notification(user_or_users, title, body, notification_type='general', library_verse=None, extra_data=None):
    """
    Saves a Notification record in the database for each user, and attempts
    to send a real-time push notification using Firebase Admin SDK Cloud Messaging (FCM).

    Parameters:
    - user_or_users: A single User instance, list of User instances, or QuerySet.
    - title: Title of the notification.
    - body: Description / message body.
    - notification_type: Type of notification (e.g. 'book_added', 'payment_created', etc.).
    - library_verse: Optional Verse object if related to a specific verse.
    - extra_data: Dict containing extra context metadata.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Normalize users input into a list/queryset
    if isinstance(user_or_users, User):
        users = [user_or_users]
    elif hasattr(user_or_users, '__iter__') and not isinstance(user_or_users, str):
        users = list(user_or_users)
    else:
        users = [user_or_users]

    if not users:
        return

    # Create notifications in bulk in the DB
    notifications_to_create = []
    for u in users:
        notifications_to_create.append(
            Notification(
                user=u,
                title=title,
                body=body,
                library_verse=library_verse,
                notification_type=notification_type,
                extra_data=extra_data or {},
                is_read=False
            )
        )
    Notification.objects.bulk_create(notifications_to_create)

    # Fetch registered FCM device tokens for these users
    tokens = list(FCMDevice.objects.filter(user__in=users).values_list('token', flat=True))
    if not tokens:
        logger.info("No FCM tokens registered for user(s). DB notification saved.")
        return

    # Ensure Firebase Admin SDK is initialized
    try:
        from settings.firebase_init import initialize_firebase
        initialize_firebase()
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        print(f"[Firebase SDK Init Failure] Cannot send push notification: {e}")
        return

    # Send push notifications via Firebase Admin SDK
    try:
        from firebase_admin import messaging

        fcm_notification = messaging.Notification(
            title=title,
            body=body
        )

        # Prepare stringified key-value data payload for FCM
        fcm_data = {
            "notification_type": str(notification_type),
            "title": str(title),
            "body": str(body)
        }
        if extra_data:
            for k, v in extra_data.items():
                fcm_data[str(k)] = str(v)

        # Firebase multicast message has a token limit of 500 per request
        for i in range(0, len(tokens), 500):
            token_chunk = tokens[i:i+500]
            message = messaging.MulticastMessage(
                notification=fcm_notification,
                data=fcm_data,
                tokens=token_chunk
            )
            response = messaging.send_multicast(message)
            
            logger.info(f"FCM multicast batch sent. Success: {response.success_count}, Failure: {response.failure_count}")
            print(f"[Firebase Messaging] Sent '{title}' successfully to {response.success_count} devices, failed for {response.failure_count}.")
            
            # Clean up unregistered/invalid tokens if any failed
            if response.failure_count > 0:
                for idx, resp in enumerate(response.responses):
                    if not resp.success:
                        # Grab token that failed
                        bad_token = token_chunk[idx]
                        # Remove bad tokens from the DB to keep clean
                        FCMDevice.objects.filter(token=bad_token).delete()
                        logger.info(f"Removed invalid/expired FCM device token from database.")
                        
    except Exception as e:
        logger.exception("Failed to send push notifications via Firebase Admin SDK.")
        print(f"[Firebase Messaging Exception] {str(e)}")
