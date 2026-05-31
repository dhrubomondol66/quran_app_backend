from django.shortcuts import render
import os
import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from drf_yasg.utils import swagger_auto_schema
from users.models import User
from django.utils import timezone
from datetime import timedelta
from users.email_service import send_password_reset_email
from users.serializers import UserLoginSerializer, UserSerializer, ForgotPasswordSerializer, ChangePasswordSerializer
from .models import Overview, UserManagement, ProfileSettings, LibraryContent, SubscriptionPlan
from .serializers import OverviewSerializer, UserManagementSerializer, ProfileSettingsSerializer, LibraryContentSerializer, SubscriptionPlanSerializer

class OverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.contrib.auth import get_user_model
        User = get_user_model()

        all_users = User.objects.filter(is_admin=False)
        total_users = all_users.count()

        premium_users = UserManagement.objects.filter(
            user__is_admin=False,
            subscription_status='premium'
        ).count()

        free_users = UserManagement.objects.filter(
            user__is_admin=False,
            subscription_status='free'
        ).count()

        # Growth: compare this month's signups vs last month's
        now = timezone.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

        this_month_users = all_users.filter(date_joined__gte=this_month_start).count()
        last_month_users = all_users.filter(
            date_joined__gte=last_month_start,
            date_joined__lt=this_month_start
        ).count()

        if last_month_users > 0:
            user_growth = round(((this_month_users - last_month_users) / last_month_users) * 100, 2)
        else:
            user_growth = 100.0 if this_month_users > 0 else 0.0

        # Revenue and earnings — update price per premium user to match your actual plan price
        PREMIUM_PRICE = 9.99
        revenue = round(premium_users * PREMIUM_PRICE)
        total_earn = revenue  # adjust if you have a separate earnings model

        data = {
            'total_users': total_users,
            'total_earn': total_earn,
            'premium_users': premium_users,
            'free_users': free_users,
            'user_growth': user_growth,
            'revenue': revenue,
        }

        serializer = OverviewSerializer(data)
        return Response(serializer.data)

class UserManagementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Auto-create UserManagement for any user that doesn't have one yet
        users = User.objects.filter(is_admin=False)
        for user in users:
            UserManagement.objects.get_or_create(user=user)

        user_management_qs = UserManagement.objects.select_related('user').filter(
            user__is_admin=False
        )
        serializer = UserManagementSerializer(user_management_qs, many=True)
        return Response(serializer.data)

    def put(self, request, user_id):
        try:
            user_management = UserManagement.objects.get(user__id=user_id, user__is_admin=False)
        except UserManagement.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserManagementSerializer(user_management, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_management = serializer.save()
        # Suspend action – deactivate and revoke tokens
        if user_management.actions == 'suspended':
            user_management.user.is_active = False
            user_management.user.save(update_fields=['is_active'])
            try:
                from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
                OutstandingToken.objects.filter(user=user_management.user).delete()
            except Exception:
                pass
        # Delete action – permanently remove user
        elif user_management.actions == 'delete':
            user_management.user.delete()
            return Response({'message': 'User permanently deleted'}, status=status.HTTP_200_OK)
        # Active action – reactivate user
        elif user_management.actions == 'active':
            user_management.user.is_active = True
            user_management.user.save(update_fields=['is_active'])
        return Response(UserManagementSerializer(user_management).data, status=status.HTTP_200_OK)

class ProfileSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile_settings, _ = ProfileSettings.objects.get_or_create(
            user=request.user,
            defaults={
                'email': request.user.email,
                'is_admin': request.user.is_admin,
                'is_active': request.user.is_active,
            }
        )
        serializer = ProfileSettingsSerializer(profile_settings)
        return Response(serializer.data)

    def put(self, request):
        profile_settings, _ = ProfileSettings.objects.get_or_create(user=request.user)

        serializer = ProfileSettingsSerializer(
            profile_settings,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            "message": "Updated successfully",
            "email": profile_settings.user.email
        })

class AdminLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=UserLoginSerializer)
    def post(self, request):
        """Login admin using hard‑coded credentials from settings and return JWT tokens.
        Single admin only (no subadmins).
        If the admin user does not exist in the database, it will be created on‑the‑fly.
        """
        from django.conf import settings
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'error': 'Email and password required'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Get single admin email from settings
        admin_email = settings.ADMIN_EMAIL.strip()
        if email != admin_email:
            return Response({'error': 'Admin email not authorized'},
                            status=status.HTTP_403_FORBIDDEN)

        # Retrieve or create the admin user. Use set_password to hash the env password.
        admin_user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'is_admin': True,
            },
        )
        if created:
            # Initialise password to the env value for the first login
            admin_user.set_password(settings.ADMIN_PASSWORD)
            admin_user.is_admin = True
            admin_user.save()
        else:
            # Ensure role flag is up‑to‑date
            if not admin_user.is_admin:
                admin_user.is_admin = True
                admin_user.save(update_fields=['is_admin'])

        # Verify the supplied password against the stored hash
        if not admin_user.check_password(password):
            return Response({'error': 'Invalid admin credentials'},
                            status=status.HTTP_403_FORBIDDEN)

        # Issue JWT tokens
        refresh = RefreshToken.for_user(admin_user)
        return Response({
            'message': 'Admin login successful',
            'user': UserSerializer(admin_user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        })

class AdminForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ForgotPasswordSerializer)
    def post(self, request):
        """Send password reset email to admin."""
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        admin_user = User.objects.filter(email=email, is_admin=True).first()
        if not admin_user:
            return Response({'error': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)

        token = default_token_generator.make_token(admin_user)

        # Get frontend URL (admin dashboard URL)
        frontend_url = request.data.get('frontend_url', 'http://localhost:3000')

        # ← Use the same email service as users (sends full HTML email with button)
        email_sent = send_password_reset_email(
            user=admin_user,
            reset_token=token,
            frontend_url=f"{frontend_url}/admin-dashboard"  # admin reset page
        )

        if email_sent:
            return Response({
                'message': 'Password reset email sent successfully',
                'reset_url': f'{frontend_url}/admin-dashboard/admin-reset-password?email={admin_user.email}&token={token}'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': 'Failed to send password reset email'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class AdminResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(request_body=ChangePasswordSerializer)
    def post(self, request):
        """Reset admin password using token and new password."""
        email = request.data.get('email')
        token = request.data.get('token')
        if not email or not token:
            return Response({'error': 'Email and token are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Locate the admin user (is_admin flag)
        admin_user = User.objects.filter(email=email, is_admin=True).first()
        if not admin_user:
            return Response({'error': 'Admin not found'}, status=status.HTTP_404_NOT_FOUND)

        # Verify token
        if not default_token_generator.check_token(admin_user, token):
            return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate new password
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_user.set_password(serializer.validated_data['new_password'])
        admin_user.save()
        return Response({'message': 'Password reset successful'}, status=status.HTTP_200_OK)

class LibraryContentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        content_type = request.query_params.get('type')       # filter: pdf / audio / book
        access       = request.query_params.get('access')     # filter: free / premium

        qs = LibraryContent.objects.all().order_by('-created_at')
        if content_type:
            qs = qs.filter(content_type=content_type)
        if access:
            qs = qs.filter(access=access)

        serializer = LibraryContentSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request):
        # multipart/form-data because of file upload
        serializer = LibraryContentSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save(uploaded_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LibraryContentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_object(self, pk):
        try:
            return LibraryContent.objects.get(pk=pk)
        except LibraryContent.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        return Response(LibraryContentSerializer(obj, context={'request': request}).data)

    def put(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = LibraryContentSerializer(obj, data=request.data, partial=True, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        # delete files from storage too
        obj.file.delete(save=False)
        if obj.cover_image:
            obj.cover_image.delete(save=False)
        obj.delete()
        return Response({'message': 'Deleted successfully'}, status=status.HTTP_200_OK)


# ── Subscription Pricing ──────────────────────────────────────────────────────

class SubscriptionPlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.all().order_by('interval')
        return Response(SubscriptionPlanSerializer(plans, many=True).data)

    def post(self, request):
        """Create or update a plan and sync price to Stripe."""
        serializer = SubscriptionPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        interval = serializer.validated_data['interval']
        price    = serializer.validated_data['price']

        plan, _ = SubscriptionPlan.objects.get_or_create(interval=interval)
        plan.price       = price
        plan.is_active   = serializer.validated_data.get('is_active', True)
        plan.updated_by  = request.user

        stripe_price_id = self._sync_stripe_price(plan, price)
        if stripe_price_id:
            plan.stripe_price_id = stripe_price_id

        plan.save()
        return Response(SubscriptionPlanSerializer(plan).data, status=status.HTTP_200_OK)

    def _sync_stripe_price(self, plan, new_price):
        """
        Stripe prices are immutable — archive the old one and create a new one.
        Returns the new stripe price id or None on error.
        """
        try:
            # Archive old price so it no longer appears in checkout
            if plan.stripe_price_id:
                stripe.Price.modify(plan.stripe_price_id, active=False)

            # Create new recurring price
            stripe_price = stripe.Price.create(
                currency='usd',
                unit_amount=int(new_price * 100),       # cents
                recurring={'interval': 'month' if plan.interval == 'monthly' else 'year'},
                product_data={'name': f'{plan.interval.capitalize()} Subscription'},
            )
            return stripe_price.id
        except stripe.error.StripeError as e:
            # Log but don't crash — price still saved locally
            print(f"Stripe sync error: {e}")
            return None


class SubscriptionPlanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if 'price' in serializer.validated_data:
            stripe_price_id = SubscriptionPlanView._sync_stripe_price(self, plan, serializer.validated_data['price'])
            if stripe_price_id:
                plan.stripe_price_id = stripe_price_id

        plan.updated_by = request.user
        serializer.save()
        return Response(SubscriptionPlanSerializer(plan).data)

    def delete(self, request, pk):
        try:
            plan = SubscriptionPlan.objects.get(pk=pk)
        except SubscriptionPlan.DoesNotExist:
            return Response({'error': 'Plan not found'}, status=status.HTTP_404_NOT_FOUND)

        if plan.stripe_price_id:
            try:
                stripe.Price.modify(plan.stripe_price_id, active=False)
            except stripe.error.StripeError:
                pass

        plan.delete()
        return Response({'message': 'Plan deleted'}, status=status.HTTP_200_OK)