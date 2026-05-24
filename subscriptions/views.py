import stripe
from django.conf import settings
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

        price_map = {
            "monthly": settings.STRIPE_MONTHLY_PRICE_ID,
            "yearly":  settings.STRIPE_YEARLY_PRICE_ID,
        }

        # DEBUG: Print what we received and what settings contain
        print("\n=== DEBUG CreateSubscriptionView ===")
        print(f"Plan received: {plan}")
        print(f"Price map: {price_map}")
        print(f"Request data: {request.data}")
        print(f"Settings STRIPE_MONTHLY_PRICE_ID: {settings.STRIPE_MONTHLY_PRICE_ID}")
        print(f"Settings STRIPE_YEARLY_PRICE_ID: {settings.STRIPE_YEARLY_PRICE_ID}")
        print("=====================================\n")

        if plan not in price_map:
            return Response(
                {"detail": "Invalid plan. Choose 'monthly' or 'yearly'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent duplicate active subscriptions
        existing = request.user.subscription.first()
        if existing and existing.is_valid():
            return Response(
                {"detail": "You already have an active subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = stripe.checkout.Session.create(
                mode="subscription",
                payment_method_types=["card"],
                line_items=[{"price": price_map[plan], "quantity": 1}],
                success_url="http://localhost:3000/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="http://localhost:3000/cancel",
                metadata={
                    "user_id": str(request.user.id),
                    "plan": plan,
                },
            )
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"checkout_url": session.url})


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