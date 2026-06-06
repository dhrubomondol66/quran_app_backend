from django.urls import path
from .views import (
    OverviewView,
    UserManagementView,
    ProfileSettingsView,
    AdminLoginView,
    AdminForgotPasswordView,
    AdminResetPasswordView,
    LibraryContentView,
    LibraryContentDetailView,
    SubscriptionPlanView,
    SubscriptionPlanDetailView,
    UserManagementActionView
)

urlpatterns = [
    # Auth
    path('admin-login/',     AdminLoginView.as_view(),          name='admin-login'),
    path('forgot-password/', AdminForgotPasswordView.as_view(), name='admin-forgot-password'),
    path('reset-password/',  AdminResetPasswordView.as_view(),  name='admin-reset-password'),

    # Dashboard
    path('overview/',               OverviewView.as_view(),              name='overview'),
    path('user-management/',        UserManagementView.as_view(),        name='user-management'),
    path('user-management/<int:user_id>/<str:action>/', UserManagementActionView.as_view(), name='user-management-action'),
    path('profile-settings/',       ProfileSettingsView.as_view(),        name='profile-settings'),

    # Library
    path('library/',           LibraryContentView.as_view(),         name='library-list'),
    path('library/<int:pk>/',  LibraryContentDetailView.as_view(),   name='library-detail'),

    # Subscription pricing
    path('subscription-plans/',           SubscriptionPlanView.as_view(),        name='subscription-plans'),
    path('subscription-plans/<int:pk>/',  SubscriptionPlanDetailView.as_view(),  name='subscription-plan-detail'),
]