from django.urls import path
from .views import UserProfileView, HomeContentView

urlpatterns = [
    path('user-profile/', UserProfileView.as_view()),
    path('home-content/', HomeContentView.as_view()),
]