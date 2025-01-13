from django.urls import path, include
from .views import PropertyListView, PropertyDetailView, PropertyTypeListView, PropertyImageCreateView, PropertyImageDeleteView
from .views import FavoriteViewSet
from rest_framework.routers import DefaultRouter

# Initialize the router and register the FavoriteViewSet
router = DefaultRouter()
router.register(r'favorites', FavoriteViewSet, basename='favorite')

urlpatterns = [
    # Existing property-related URLs
    path('properties/', PropertyListView.as_view(), name='property-list'),
    path('properties/<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('property-types/', PropertyTypeListView.as_view(), name='property-types'),
    path('property-images/', PropertyImageCreateView.as_view(), name='property-images-create'),
    path('property-images/<int:pk>/delete/', PropertyImageDeleteView.as_view(), name='property-image-delete'),

    # Add the favorites routes
    path('', include(router.urls)),  # Include the favorite-related routes
]
