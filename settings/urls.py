from django.urls import path
from .views import (
    SettingsView,
    NotificationView,
    AddFeatureView,
    FeedbackView,
    DeleteAccountView,
    FCMDeviceRegisterView,
    AppRatingView,
)

urlpatterns = [
    path('settings/', SettingsView.as_view()),
    path('notifications/', NotificationView.as_view()),
    path('notifications/register-device/', FCMDeviceRegisterView.as_view()),
    path('add-feature/', AddFeatureView.as_view()),
    path('feedback/', FeedbackView.as_view()),
    path('delete-account/', DeleteAccountView.as_view()),
    path('rate-app/', AppRatingView.as_view()),
]