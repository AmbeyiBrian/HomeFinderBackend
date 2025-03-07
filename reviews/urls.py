from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReviewViewSet, RequestsListCreateView, RequestsDetailView

# Initialize the router
router = DefaultRouter()

# Register the Review viewset with the router
router.register(r'reviews', ReviewViewSet)

# Define the URL patterns
urlpatterns = [
    path('', include(router.urls)),
    path('requests/', RequestsListCreateView.as_view(), name='requests-list-create'),
    path('requests/<int:pk>/', RequestsDetailView.as_view(), name='requests-detail'),

]
