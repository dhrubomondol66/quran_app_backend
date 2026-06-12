from django.urls import path
from .views import UserProgressView, LogReadingView

urlpatterns = [
    path("", UserProgressView.as_view()),
    path("log/", LogReadingView.as_view()),
]