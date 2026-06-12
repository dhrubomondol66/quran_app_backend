from django.urls import path
from .views import UserProgressView, LogReadingView, GlobalLeaderboardView

urlpatterns = [
    path("", UserProgressView.as_view()),
    path("log/", LogReadingView.as_view()),
    path("leaderboard/", GlobalLeaderboardView.as_view()),
]