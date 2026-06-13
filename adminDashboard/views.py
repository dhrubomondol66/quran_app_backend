from django.shortcuts import render
import os
import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
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
            user = User.objects.get(id=user_id)
            user_management, _ = UserManagement.objects.get_or_create(user=user)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = UserManagementSerializer(user_management, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Handle password update before saving
        password = serializer.validated_data.pop('password', None)
        if password:
            user_management.user.set_password(password)
            user_management.user.save(update_fields=['password'])

        action = serializer.validated_data.get('actions', user_management.actions)

        if action == 'delete':
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=user_management.user,
                    title="Account Deleted",
                    body="Your account has been permanently deleted by the administrator.",
                    notification_type='user_deleted'
                )
            except Exception as e:
                print(f"Failed to send account deletion notification: {e}")

            user_management.user.delete()
            return Response({'message': 'User permanently deleted'}, status=status.HTTP_200_OK)

        if action == 'suspend':
            user_management.user.is_active = False
            user_management.user.save(update_fields=['is_active'])
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=user_management.user,
                    title="Account Suspended",
                    body="Your account has been suspended by the administrator. Please contact support.",
                    notification_type='user_suspended'
                )
            except Exception as e:
                print(f"Failed to send account suspension notification: {e}")

            try:
                from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
                OutstandingToken.objects.filter(user=user_management.user).delete()
            except Exception:
                pass

        # Activate: re-enable account
        elif action == 'active':
            user_management.user.is_active = True   
            user_management.user.save(update_fields=['is_active'])

        serializer.save()
        return Response(UserManagementSerializer(user_management).data, status=status.HTTP_200_OK)

class UserManagementActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id, action):  # ← make sure it's 'post' not 'put'
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        try:
            user = User.objects.get(id=user_id)
            user_management, _ = UserManagement.objects.get_or_create(user=user)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'delete':
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=user_management.user,
                    title="Account Deleted",
                    body="Your account has been permanently deleted by the administrator.",
                    notification_type='user_deleted'
                )
            except Exception as e:
                print(f"Failed to send account deletion notification (action): {e}")

            user_management.user.delete()
            return Response({'message': 'User permanently deleted'}, status=status.HTTP_200_OK)

        if action == 'suspend':
            user_management.user.is_active = False
            user_management.user.save(update_fields=['is_active'])
            user_management.actions = 'suspend'
            try:
                from settings.notifications import send_push_notification
                send_push_notification(
                    user_or_users=user_management.user,
                    title="Account Suspended",
                    body="Your account has been suspended by the administrator. Please contact support.",
                    notification_type='user_suspended'
                )
            except Exception as e:
                print(f"Failed to send account suspension notification (action): {e}")

            try:
                from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
                OutstandingToken.objects.filter(user=user_management.user).delete()
            except Exception:
                pass

        elif action == 'active':
            user_management.user.is_active = True
            user_management.user.save(update_fields=['is_active'])
            user_management.actions = 'active'

        elif action == 'reset_data':
            # 1. Reset progress/activities
            from progress.models import UserProgress, ReadVerse, ReadingLog, UserSurahCompletion, UserAchievement
            UserProgress.objects.filter(user=user).delete()
            ReadVerse.objects.filter(user=user).delete()
            ReadingLog.objects.filter(user=user).delete()
            UserSurahCompletion.objects.filter(user=user).delete()
            UserAchievement.objects.filter(user=user).delete()

            # 2. Reset community / leaderboard
            from community.models import LeaderBoard, CommunityMembers, InviteMembers, CommunityPosts, JoinRequest
            LeaderBoard.objects.filter(user=user).delete()
            CommunityMembers.objects.filter(user=user).delete()
            InviteMembers.objects.filter(user=user).delete()
            CommunityPosts.objects.filter(user=user).delete()
            JoinRequest.objects.filter(user=user).delete()

            # 3. Reset subscription / payment history
            from subscriptions.models import Subscription, PaymentHistory
            Subscription.objects.filter(user=user).delete()
            PaymentHistory.objects.filter(user=user).delete()

            user_management.actions = 'reset_data'
            user_management.save()

            return Response({
                'message': 'User data reset successfully',
                'user_id': user_id,
                'status': 'reset_data',
            }, status=status.HTTP_200_OK)

        user_management.save()
        return Response({
            'message': f'User {action} successfully',
            'user_id': user_id,
            'status': action,
        }, status=status.HTTP_200_OK)

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

    @swagger_auto_schema(request_body=ProfileSettingsSerializer)
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
    parser_classes = [MultiPartParser, FormParser]

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

    @swagger_auto_schema(request_body=LibraryContentSerializer)
    def post(self, request):
        # multipart/form-data because of file upload
        serializer = LibraryContentSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        library_item = serializer.save(uploaded_by=request.user)

        # Notify users if a new item is added to the library
        try:
            from django.contrib.auth import get_user_model
            from settings.notifications import send_push_notification
            User = get_user_model()
            active_users = User.objects.filter(is_active=True, is_admin=False)
            
            if library_item.content_type == 'audio':
                title = "New Audio Added"
                body = f"New audio added: '{library_item.title}'. Check it out!"
                notif_type = 'audio_added'
            elif library_item.content_type == 'book':
                title = "New Book Added"
                body = f"New book added: '{library_item.title}'. Check it out!"
                notif_type = 'book_added'
            else:  # pdf or fallback
                title = "New Book Added"
                body = f"New book added: '{library_item.title}'. Check it out!"
                notif_type = 'book_added'

            send_push_notification(
                user_or_users=active_users,
                title=title,
                body=body,
                notification_type=notif_type,
                extra_data={'library_id': library_item.id}
            )
        except Exception as e:
            print(f"Failed to send new library item notification: {e}")

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LibraryContentDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

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

    @swagger_auto_schema(request_body=LibraryContentSerializer)
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

    @swagger_auto_schema(request_body=SubscriptionPlanSerializer)
    def post(self, request):
        """Create or update a plan and sync price to Stripe."""
        serializer = SubscriptionPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        interval = serializer.validated_data['interval']
        price    = serializer.validated_data['price']

        plan, _ = SubscriptionPlan.objects.get_or_create(interval=interval, defaults={'price': price})
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

    @swagger_auto_schema(request_body=SubscriptionPlanSerializer)
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

class AdminAddFeatureView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
        
        from settings.models import AddFeature
        from settings.serializers import AdminAddFeatureSerializer
        features = AddFeature.objects.all().select_related('user').order_by('-created_at')
        serializer = AdminAddFeatureSerializer(features, many=True)
        return Response(serializer.data)

class AdminAppRatingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        from settings.models import AppRating
        from settings.serializers import AppRatingSerializer
        ratings = AppRating.objects.all().select_related('user').order_by('-created_at')
        serializer = AppRatingSerializer(ratings, many=True)
        return Response(serializer.data)

class AdminPaymentHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)

        from subscriptions.models import PaymentHistory
        from subscriptions.serializers import PaymentHistorySerializer
        history = PaymentHistory.objects.all().select_related('user').order_by('-created_at')
        serializer = PaymentHistorySerializer(history, many=True)
        return Response(serializer.data)