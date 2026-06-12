import stripe
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import Subscription, PaymentHistory
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
        sub, _ = Subscription.objects.update_or_create(
            user=user,
            defaults={
                "stripe_subscription_id": stripe_sub_id,
                "stripe_customer_id": stripe_cust_id,
                "plan": plan,
                "is_active": True,
                "expires_at": expires_at,
            },
        )

        # Record payment history
        PaymentHistory.objects.create(
            user=user,
            stripe_invoice_id=obj.get("invoice", "") or "",
            amount=obj.get("amount_total", 0) / 100,
            currency=obj.get("currency", "usd"),
            status="paid",
            plan=plan
        )

        try:
            from settings.notifications import send_push_notification
            admins = User.objects.filter(is_admin=True)
            amount = obj.get("amount_total", 0) / 100
            send_push_notification(
                user_or_users=admins,
                title="New Subscription Payment",
                body=f"User {user.username} successfully paid ${amount:.2f} for a '{plan}' subscription.",
                notification_type='payment_created',
                extra_data={'user_id': user.id, 'plan': plan, 'amount': amount}
            )
        except Exception as e:
            print(f"Failed to send admin payment notification: {e}")

    # ── Renewal succeeded → extend expiry ──────────────────────────────────
    elif event_type == "invoice.paid":
        stripe_sub_id = obj.get("subscription")
        if stripe_sub_id:
            stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
            expires_at = timezone.datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            )
            sub = Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).first()
            if sub:
                sub.is_active = True
                sub.expires_at = expires_at
                sub.save()
                PaymentHistory.objects.create(
                    user=sub.user,
                    stripe_invoice_id=obj.get("id", ""),
                    amount=obj.get("amount_paid", 0) / 100,
                    currency=obj.get("currency", "usd"),
                    status="paid",
                    plan=sub.plan
                )

    # ── Payment failed → deactivate ─────────────────────────────────────────
    elif event_type == "invoice.payment_failed":
        stripe_sub_id = obj.get("subscription")
        if stripe_sub_id:
            sub = Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).first()
            if sub:
                sub.is_active = False
                sub.save()
                PaymentHistory.objects.create(
                    user=sub.user,
                    stripe_invoice_id=obj.get("id", ""),
                    amount=obj.get("amount_due", 0) / 100,
                    currency=obj.get("currency", "usd"),
                    status="failed",
                    plan=sub.plan
                )

    # ── Cancelled → deactivate ──────────────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = obj.get("id")
        if stripe_sub_id:
            Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
                is_active=False,
            )

    return HttpResponse(status=200)