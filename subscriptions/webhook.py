import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import Subscription
from django.contrib.auth import get_user_model

User = get_user_model()

stripe.api_key = settings.STRIPE_SECRET_KEY


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    event_type = event["type"]
    obj = event["data"]["object"]

    # ── Payment succeeded → activate subscription ──────────────────────────
    if event_type == "checkout.session.completed":
        user_id = obj["metadata"]["user_id"]
        plan = obj["metadata"]["plan"]
        stripe_sub_id = obj["subscription"]
        stripe_cust_id = obj["customer"]

        # Fetch current_period_end directly from Stripe — source of truth
        stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
        expires_at = timezone.datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        )

        user = User.objects.get(id=user_id)
        Subscription.objects.update_or_create(
            user=user,
            defaults={
                "stripe_subscription_id": stripe_sub_id,
                "stripe_customer_id": stripe_cust_id,
                "plan": plan,
                "is_active": True,
                "expires_at": expires_at,
            },
        )

    # ── Renewal succeeded → extend expiry ──────────────────────────────────
    elif event_type == "invoice.paid":
        stripe_sub_id = obj.get("subscription")
        if stripe_sub_id:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            expires_at = timezone.datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            )
            Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
                is_active=True,
                expires_at=expires_at,
            )

    # ── Payment failed → deactivate ─────────────────────────────────────────
    elif event_type == "invoice.payment_failed":
        stripe_sub_id = obj.get("subscription")
        if stripe_sub_id:
            Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
                is_active=False,
            )

    # ── Cancelled → deactivate ──────────────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = obj.get("id")
        if stripe_sub_id:
            Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
                is_active=False,
            )

    return HttpResponse(status=200)