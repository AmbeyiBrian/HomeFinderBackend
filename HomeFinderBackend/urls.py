from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import HealthCheckView
from django.http import JsonResponse

# OpenAPI schema view setup
schema_view = get_schema_view(
   openapi.Info(
      title="HomeFinder API",
      default_version='v1',
      description="API for HomeFinder Real Estate Platform",
      terms_of_service="https://www.homefinder.com/terms/",
      contact=openapi.Contact(email="contact@homefinder.com"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

def health_check(request):
    """Health check endpoint for AWS deployment validation"""
    return JsonResponse({"status": "healthy"}, status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/users/', include('users.urls')),
    path('api/properties/', include('properties.urls')),
    path('api/reviews/', include('reviews.urls')),
    path('api/chatbot/', include('chatbot.urls')),
    path('api/payments/', include('payments.urls')),  # Add payments URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('health/', health_check, name='health_check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
