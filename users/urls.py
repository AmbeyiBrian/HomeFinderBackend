from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, UserDetailView, TokenObtainPairWithUserDetailsView, TokenRefreshWithUserDetailsView, change_password
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny

# Swagger schema view
schema_view = get_schema_view(
    openapi.Info(
        title="HomeFinder API",
        default_version='v1',
        description="API documentation for HomeFinder/MapNest",
    ),
    public=True,
    permission_classes=[AllowAny],
)

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', include(router.urls)),  # Include user-related endpoints
    path('api/token/', TokenObtainPairWithUserDetailsView.as_view(), name='token_obtain_pair'),  # For login
    path('api/token/refresh/', TokenRefreshWithUserDetailsView.as_view(), name='token_refresh'),  # Refresh token
    path('api/token/verify/', TokenRefreshWithUserDetailsView.as_view(), name='token_verify'),  # Verify token
    path('api/user/', UserDetailView.as_view(), name='user_detail'),  # New endpoint for user details
    path('users/profile/change-password/', change_password, name='change-password'),
    # Swagger endpoints
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]
