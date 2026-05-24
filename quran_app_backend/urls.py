"""
URL configuration for quran_app_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from users.urls import urlpatterns as users_urlpatterns
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings
from django.conf.urls.static import static

schema_view = get_schema_view(
   openapi.Info(
      title="Quran App API",
      default_version='v1',
      description="API documentation for Quran App Backend",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path('admin-dashboard/', include('adminDashboard.urls')),
    path('auth/', include('users.urls')),
    path('home/', include('home.urls')),
    path('library/', include('library.urls')),
    path('community/', include('community.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('progress/', include('progress.urls')),
    path('settings/', include('settings.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema_swagger'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema_redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
