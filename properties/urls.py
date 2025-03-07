from django.urls import path, include
from .views import (
    PropertyListView,
    PropertyDetailView,
    PropertyTypeListView,
    PropertyImageCreateView,
    PropertyImageDeleteView,
    PropertyImageListView,
    FavoriteViewSet,
    UserPropertyListView,
    ReservationViewSet,
    PropertyAvailabilityView
)
from rest_framework.routers import DefaultRouter

# Initialize the router and register viewsets
router = DefaultRouter()
router.register(r'favorites', FavoriteViewSet, basename='favorite')
router.register(r'reservations', ReservationViewSet, basename='reservation')

urlpatterns = [
    # Existing property-related URLs
    path('properties/', PropertyListView.as_view(), name='property-list'),
    path('properties/<int:pk>/', PropertyDetailView.as_view(), name='property-detail'),
    path('property-types/', PropertyTypeListView.as_view(), name='property-types'),
    path('my-properties/', UserPropertyListView.as_view(), name='user-properties'),
    path('property-images/', PropertyImageCreateView.as_view(), name='property-images-create'),
    path('property-images/<int:pk>/delete/', PropertyImageDeleteView.as_view(), name='property-image-delete'),
    path('property-images/list/', PropertyImageListView.as_view(), name='property-images-list'),
    
    # New reservation-related URL
    path('property-availability/', PropertyAvailabilityView.as_view(), name='property-availability'),

    # Include router URLs (favorites and reservations)
    path('', include(router.urls)),
]