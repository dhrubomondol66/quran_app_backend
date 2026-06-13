import json
from datetime import datetime, timezone as datetime_timezone
import stripe
from django.conf import settings
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import Subscription, PaymentHistory
from .serializers import SubscriptionSerializer, PaymentHistorySerializer
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

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['plan'],
            properties={
                'plan': openapi.Schema(type=openapi.TYPE_STRING, description="Choose 'monthly' or 'yearly'"),
            }
        )
    )
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
                    stripe_sub.current_period_end, tz=datetime_timezone.utc
                )
                sub.save()

                # Log payment history
                amount = invoice.get("amount_paid", 0) / 100
                PaymentHistory.objects.create(
                    user=sub.user,
                    stripe_invoice_id=invoice.get("id", ""),
                    amount=amount,
                    currency=invoice.get("currency", "usd"),
                    status="paid",
                    plan=sub.plan
                )

                try:
                    from django.contrib.auth import get_user_model
                    from settings.notifications import send_push_notification
                    User = get_user_model()
                    admins = User.objects.filter(is_admin=True)
                    send_push_notification(
                        user_or_users=admins,
                        title="New Subscription Payment",
                        body=f"User {sub.user.username} successfully paid ${amount:.2f} for a '{sub.plan}' subscription.",
                        notification_type='payment_created',
                        extra_data={'user_id': sub.user.id, 'plan': sub.plan, 'amount': amount}
                    )
                except Exception as e:
                    print(f"Failed to send admin payment notification from webhook view: {e}")

            except Subscription.DoesNotExist:
                pass

        elif event["type"] == "invoice.payment_failed":
            invoice = event["data"]["object"]
            stripe_sub_id = invoice.get("subscription")
            try:
                sub = Subscription.objects.get(stripe_subscription_id=stripe_sub_id)
                sub.is_active = False
                sub.save()
                PaymentHistory.objects.create(
                    user=sub.user,
                    stripe_invoice_id=invoice.get("id", ""),
                    amount=invoice.get("amount_due", 0) / 100,
                    currency=invoice.get("currency", "usd"),
                    status="failed",
                    plan=sub.plan
                )
            except Subscription.DoesNotExist:
                pass

        elif event["type"] == "customer.subscription.deleted":
            stripe_sub_id = event["data"]["object"]["id"]
            Subscription.objects.filter(
                stripe_subscription_id=stripe_sub_id
            ).update(is_active=False)

        return Response({"status": "ok"})

class UserSubscriptionPlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from adminDashboard.models import SubscriptionPlan
        from adminDashboard.serializers import SubscriptionPlanSerializer
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('interval')
        return Response(SubscriptionPlanSerializer(plans, many=True).data)

class ToggleAutoRenewalView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['auto_renew'],
            properties={
                'auto_renew': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Enable or disable auto-renewal'),
            }
        )
    )
    def post(self, request):
        subscription = request.user.subscription.first()
        if not subscription or not subscription.stripe_subscription_id:
            return Response({"detail": "No active subscription found."}, status=status.HTTP_404_NOT_FOUND)

        auto_renew = request.data.get('auto_renew')
        if auto_renew is None:
            return Response({"detail": "auto_renew parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=not auto_renew
            )
            subscription.auto_renew = auto_renew
            subscription.save()
            return Response({
                "message": f"Auto-renewal {'enabled' if auto_renew else 'disabled'} successfully.",
                "auto_renew": subscription.auto_renew
            })
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = PaymentHistory.objects.filter(user=request.user).order_by('-created_at')
        serializer = PaymentHistorySerializer(history, many=True)
        return Response(serializer.data)

class RestoreSubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        try:
            customers = stripe.Customer.list(email=user.email, limit=1)
            if not customers.data:
                return Response({"detail": "No Stripe customer found for this email. Nothing to restore."}, status=status.HTTP_404_NOT_FOUND)
            
            customer_id = customers.data[0].id
            subs = stripe.Subscription.list(customer=customer_id, status='active', limit=1)
            if not subs.data:
                subs = stripe.Subscription.list(customer=customer_id, status='trialing', limit=1)
                
            if not subs.data:
                return Response({"detail": "No active or trialing Stripe subscriptions found to restore."}, status=status.HTTP_404_NOT_FOUND)
            
            stripe_sub = subs.data[0]
            plan_interval = 'monthly'
            if stripe_sub.items.data:
                price = stripe_sub.items.data[0].price
                if price.recurring:
                    plan_interval = price.recurring.interval
                    if plan_interval == 'month':
                        plan_interval = 'monthly'
                    elif plan_interval == 'year':
                        plan_interval = 'yearly'

            sub_obj, created = Subscription.objects.get_or_create(user=user)
            sub_obj.stripe_customer_id = customer_id
            sub_obj.stripe_subscription_id = stripe_sub.id
            sub_obj.plan = plan_interval
            sub_obj.is_active = True
            sub_obj.expires_at = datetime.fromtimestamp(stripe_sub.current_period_end, tz=datetime_timezone.utc)
            sub_obj.save()

            return Response({
                "message": "Subscription restored successfully.",
                "subscription": SubscriptionSerializer(sub_obj).data
            })
        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ConfirmPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['subscription_id'],
            properties={
                'subscription_id': openapi.Schema(type=openapi.TYPE_STRING, description="Stripe subscription ID to confirm"),
            }
        )
    )
    def post(self, request):
        sub_id = request.data.get("subscription_id")
        if not sub_id:
            return Response({"detail": "subscription_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            stripe_sub = stripe.Subscription.retrieve(sub_id)

            sub = Subscription.objects.filter(stripe_subscription_id=sub_id, user=request.user).first()
            if not sub:
                sub = Subscription.objects.filter(user=request.user).first()
                if not sub:
                    sub = Subscription.objects.create(user=request.user)
                sub.stripe_subscription_id = sub_id
                sub.stripe_customer_id = getattr(stripe_sub, 'customer', '') or ''

            plan_name = (stripe_sub.metadata or {}).get("plan", "monthly") if hasattr(stripe_sub, 'metadata') and stripe_sub.metadata else "monthly"
            sub.plan = plan_name

            latest_invoice_ref = getattr(stripe_sub, 'latest_invoice', None)
            amount = 20.0
            currency = "usd"
            invoice_id_str = ""
            invoice_paid = False

            if latest_invoice_ref:
                try:
                    if isinstance(latest_invoice_ref, str):
                        invoice = stripe.Invoice.retrieve(latest_invoice_ref)
                    else:
                        invoice = latest_invoice_ref

                    # Use getattr for Stripe objects (they use attribute access, not dict)
                    invoice_id_str = getattr(invoice, 'id', '') or ''
                    amount_paid_raw = getattr(invoice, 'amount_paid', None) or 0
                    amount_due_raw = getattr(invoice, 'amount_due', None) or 0
                    amount = (amount_paid_raw or amount_due_raw) / 100
                    currency = getattr(invoice, 'currency', 'usd') or 'usd'
                    invoice_status = getattr(invoice, 'status', '') or ''

                    if invoice_status == "paid" or (amount_paid_raw and amount_paid_raw > 0):
                        invoice_paid = True
                    else:
                        pay_intent_ref = getattr(invoice, 'payment_intent', None)
                        if pay_intent_ref:
                            pi_id = pay_intent_ref if isinstance(pay_intent_ref, str) else getattr(pay_intent_ref, 'id', None)
                            if pi_id:
                                pi = stripe.PaymentIntent.retrieve(pi_id)
                                if getattr(pi, 'status', '') == "succeeded":
                                    invoice_paid = True
                except Exception as ex:
                    print(f"Error checking invoice status: {ex}")
                    invoice_id_str = str(latest_invoice_ref) if isinstance(latest_invoice_ref, str) else ""

            sub_status = getattr(stripe_sub, 'status', '') or ''
            if sub_status in ["active", "trialing"] or invoice_paid:
                sub.is_active = True
                period_end = getattr(stripe_sub, 'current_period_end', None)
                if period_end:
                    sub.expires_at = datetime.fromtimestamp(
                        period_end, tz=datetime_timezone.utc
                    )
                sub.save()

                if invoice_id_str:
                    payment_exists = PaymentHistory.objects.filter(
                        user=request.user,
                        stripe_invoice_id=invoice_id_str,
                        status="paid"
                    ).exists()
                else:
                    # No invoice ID — check if any payment exists for this sub
                    payment_exists = PaymentHistory.objects.filter(
                        user=request.user,
                        plan=plan_name,
                        status="paid"
                    ).order_by('-created_at').first() is not None and \
                    PaymentHistory.objects.filter(
                        user=request.user,
                        plan=plan_name,
                        status="paid",
                        created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
                    ).exists()

                if not payment_exists:
                    PaymentHistory.objects.create(
                        user=request.user,
                        stripe_invoice_id=invoice_id_str,
                        amount=amount,
                        currency=currency,
                        status="paid",
                        plan=plan_name
                    )

                return Response({
                    "status": "success",
                    "message": "Payment confirmed and subscription activated.",
                    "subscription": SubscriptionSerializer(sub).data
                })
            else:
                # Even if subscription status is incomplete, save what we have
                sub.stripe_customer_id = getattr(stripe_sub, 'customer', '') or ''
                sub.save()
                return Response({
                    "status": sub_status,
                    "message": f"Subscription status is {sub_status}. Payment may still be processing."
                }, status=status.HTTP_400_BAD_REQUEST)

        except stripe.error.StripeError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"ConfirmPaymentView unexpected error: {e}")
            return Response({"detail": f"Server error: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)