import json
from datetime import datetime
import stripe
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subscription
from .serializers import SubscriptionSerializer
from .services import user_has_active_subscription

stripe.api_key = settings.STRIPE_SECRET_KEY


class MySubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # ← FK returns a Manager, not an instance — use .first()
        subscription = request.user.subscription.first()
        data = SubscriptionSerializer(subscription).data if subscription else None

        return Response({
            "has_active_subscription": user_has_active_subscription(request.user),
            "subscription": data,
        })


class CreateSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = request.data.get("plan")

        from adminDashboard.models import SubscriptionPlan

        db_monthly = SubscriptionPlan.objects.filter(interval="monthly", is_active=True).first()
        db_yearly = SubscriptionPlan.objects.filter(interval="yearly", is_active=True).first()

        monthly_price_id = db_monthly.stripe_price_id if db_monthly and db_monthly.stripe_price_id else settings.STRIPE_MONTHLY_PRICE_ID
        yearly_price_id = db_yearly.stripe_price_id if db_yearly and db_yearly.stripe_price_id else settings.STRIPE_YEARLY_PRICE_ID

        price_map = {
            "monthly": monthly_price_id,
            "yearly":  yearly_price_id,
        }

        if plan not in price_map:
            return Response(
                {"detail": "Invalid plan. Choose 'monthly' or 'yearly'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = request.user.subscription.first()
        if existing and existing.is_valid():
            return Response(
                {"detail": "You already have an active subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Step 1: Get or create Stripe customer
            subscription_obj = request.user.subscription.first()
            
            if subscription_obj and subscription_obj.stripe_customer_id:
                customer_id = subscription_obj.stripe_customer_id
            else:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    metadata={"user_id": str(request.user.id)}
                )
                customer_id = customer.id

            # Step 2: Create subscription with payment_behavior='default_incomplete'
            # This creates the sub WITHOUT charging — returns a PaymentIntent client_secret
            stripe_sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_map[plan]}],
                payment_behavior="default_incomplete",
                payment_settings={"save_default_payment_method": "on_subscription"},
                expand=["latest_invoice.payment_intent", "latest_invoice.confirmation_secret"],
                metadata={
                    "user_id": str(request.user.id),
                    "plan": plan,
                },
            )

            # Step 3: Save customer_id and pending subscription to DB
            if subscription_obj:
                subscription_obj.stripe_customer_id = customer_id
                subscription_obj.stripe_subscription_id = stripe_sub.id
                subscription_obj.plan = plan
                subscription_obj.is_active = False  # Not active until payment confirmed
                subscription_obj.save()
            else:
                Subscription.objects.create(
                    user=request.user,
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=stripe_sub.id,
                    plan=plan,
                    is_active=False,
                )

            # Step 4: Return client_secret to frontend/mobile to complete payment IN-APP
            latest_invoice = stripe_sub.latest_invoice
            client_secret = None

            # Try retrieving client_secret from payment_intent (older Stripe versions)
            if hasattr(latest_invoice, "payment_intent") and latest_invoice.payment_intent:
                if isinstance(latest_invoice.payment_intent, str):
                    client_secret = latest_invoice.payment_intent
                else:
                    client_secret = getattr(latest_invoice.payment_intent, "client_secret", None)

            # Try retrieving from confirmation_secret (newer Stripe versions, e.g. Basil+)
            if not client_secret and hasattr(latest_invoice, "confirmation_secret") and latest_invoice.confirmation_secret:
                client_secret = getattr(latest_invoice.confirmation_secret, "client_secret", None)

            if not client_secret:
                return Response(
                    {"detail": "Unable to retrieve payment client secret from Stripe. Please check your Stripe API version and configuration."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                "subscription_id": stripe_sub.id,
                "client_secret": client_secret,  # Use this in Stripe SDK
                "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                "plan": plan,
                "message": "Use client_secret with Stripe SDK to confirm payment in-app"
            })

        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        subscription = request.user.subscription.first()

        if not subscription or not subscription.is_valid():
            return Response(
                {"detail": "No active subscription found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscription.stripe_subscription_id:
            return Response(
                {"detail": "No Stripe subscription linked."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Cancels at period end — user keeps access until expires_at
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Subscription will cancel at the end of the billing period."})


class SuccessView(APIView):                               # ← was missing entirely
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")

        if not session_id:
            return Response({"detail": "Missing session_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        subscription = request.user.subscription.first()

        return Response({
            "detail": "Payment successful.",
            "session_status": session.status,             # "complete" if paid
            "subscription": SubscriptionSerializer(subscription).data if subscription else None,
        })


class CancelView(APIView):                                # ← was missing entirely
    def get(self, request):
        return Response({"detail": "Checkout was cancelled. No charge was made."})


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "invoice.payment_succeeded":
            invoice = event["data"]["object"]
            stripe_sub_id = invoice.get("subscription")

            try:
                sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
                stripe_sub = stripe.Subscription.retrieve(stripe_sub_id)
                
                sub.is_active = True
                sub.expires_at = datetime.fromtimestamp(
                    stripe_sub.current_period_end, tz=timezone.utc
                )
                sub.save()
            except Subscription.DoesNotExist:
                pass

        elif event["type"] == "customer.subscription.deleted":
            stripe_sub_id = event["data"]["object"]["id"]
            Subscription.objects.filter(
                stripe_subscription_id=stripe_sub_id
            ).update(is_active=False)

        return Response({"status": "ok"})