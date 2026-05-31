from django.urls import path
from .views import (
    RegisterView, 
    UserLoginView, 
    UserLogoutView, 
    UserRefreshTokenView, 
    ForgotPasswordView,
    ResetPasswordView,
    ChangePasswordView,
    ProfileView,
    UpdateProfileView,
    GoogleLoginView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('refresh/', UserRefreshTokenView.as_view(), name='refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('update_profile/', UpdateProfileView.as_view(), name='update_profile'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
]