from django.urls import path
from .views import (
    RegisterView, 
    UserLoginView, 
    UserLogoutView, 
    UserRefreshTokenView, 
    ForgotPasswordView, 
    ChangePasswordView,
    ProfileView,
    UpdateProfileView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('refresh/', UserRefreshTokenView.as_view(), name='refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('update_profile/', UpdateProfileView.as_view(), name='update_profile'),
    path('forgot_password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('change_password/', ChangePasswordView.as_view(), name='change_password'),
]