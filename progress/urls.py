from django.urls import path
from .views import UserProgressView

urlpatterns = [
    path("", UserProgressView.as_view()),
]