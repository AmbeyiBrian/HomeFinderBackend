from rest_framework import generics, status, viewsets
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError
from rest_framework.response import Response
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.conf import settings
from django.db.models import Prefetch
from .models import PropertyType, PropertyImage, Property, Favorite, Reservation
from .serializers import (
    PropertyTypeSerializer,
    PropertyImageSerializer,
    PropertySerializer,
    PropertySerializer2,
    CreateFavoriteSerializer,
    FavoriteSerializer,
    ReservationSerializer
)
from rest_framework.parsers import MultiPartParser, FormParser

CACHE_TTL = getattr(settings, 'CACHE_TTL', DEFAULT_TIMEOUT)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class PropertyListView(generics.ListCreateAPIView):
    serializer_class = PropertySerializer2
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['listing_type', 'bedrooms', 'bathrooms', 'property_type__name']
    permission_classes = [IsAuthenticatedOrReadOnly]
    authentication_classes = [JWTAuthentication]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        cache_key = f"property_list_{self.request.query_params}"
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = Property.objects.all()
            
            # Optimize query with select_related and prefetch_related
            queryset = queryset.select_related('property_type', 'owner')\
                             .prefetch_related(
                                 Prefetch('images')
                             )

            # Apply filters
            min_price = self.request.query_params.get('min_price')
            max_price = self.request.query_params.get('max_price')
            city = self.request.query_params.get('city')
            property_type = self.request.query_params.get('property_type')
            listing_type = self.request.query_params.get('listing_type')
            owner = self.request.query_params.get('owner')

            try:
                if min_price:
                    queryset = queryset.filter(price__gte=float(min_price))
                if max_price:
                    queryset = queryset.filter(price__lte=float(max_price))
                if city:
                    queryset = queryset.filter(city__icontains=city)
                if property_type:
                    queryset = queryset.filter(property_type__name__icontains=property_type)
                if listing_type:
                    queryset = queryset.filter(listing_type__icontains=listing_type)
                if owner:
                    queryset = queryset.filter(owner_id=owner)

                cache.set(cache_key, queryset, CACHE_TTL)
                
            except ValueError as e:
                print(f"Filtering error: {str(e)}")

        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

class PropertyDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Property.objects.select_related('property_type', 'owner')\
                              .prefetch_related('images')
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    authentication_classes = [JWTAuthentication]

    def get_object(self):
        obj = super().get_object()
        # Cache individual property details
        cache_key = f"property_detail_{obj.id}"
        cached_data = cache.get(cache_key)
        if cached_data is None:
            cache.set(cache_key, obj, CACHE_TTL)
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner != request.user:
            return Response(
                {"detail": "You do not have permission to update this property."},
                status=status.HTTP_403_FORBIDDEN
            )
        response = super().update(request, *args, **kwargs)
        # Invalidate cache after update
        cache.delete(f"property_detail_{instance.id}")
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner != request.user:
            return Response(
                {"detail": "You do not have permission to delete this property."},
                status=status.HTTP_403_FORBIDDEN
            )
        response = super().destroy(request, *args, **kwargs)
        # Invalidate cache after deletion
        cache.delete(f"property_detail_{instance.id}")
        return response

class PropertyTypeListView(generics.ListAPIView):
    queryset = PropertyType.objects.all()
    serializer_class = PropertyTypeSerializer
    authentication_classes = [JWTAuthentication]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        cache_key = "property_types_list"
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = PropertyType.objects.all()
            cache.set(cache_key, queryset, CACHE_TTL)
        
        return queryset

class PropertyImageListView(generics.ListAPIView):
    serializer_class = PropertyImageSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        property_id = self.request.query_params.get('property_id')
        cache_key = f"property_images_{property_id}"
        queryset = cache.get(cache_key)
        
        if queryset is None:
            queryset = PropertyImage.objects.filter(property_id=property_id)\
                                          .select_related('property')
            cache.set(cache_key, queryset, CACHE_TTL)
        
        return queryset

class PropertyImageCreateView(generics.CreateAPIView):
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer
    parser_classes = (MultiPartParser, FormParser)

    def perform_create(self, serializer):
        try:
            instance = serializer.save()
            # Invalidate image cache for this property
            cache.delete(f"property_images_{instance.property_id}")
            return instance
        except Exception as e:
            print("Error details:", str(e))
            raise ValidationError(f"Error creating property image: {str(e)}")

class PropertyImageDeleteView(generics.DestroyAPIView):
    queryset = PropertyImage.objects.all()
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            property_id = instance.property_id
            instance.delete()
            # Invalidate image cache for this property
            cache.delete(f"property_images_{property_id}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except PropertyImage.DoesNotExist:
            return Response(
                {"detail": "Property image not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Error deleting image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        # Filter favorites to return only those for the authenticated user
        return Favorite.objects.filter(user=self.request.user).select_related('property', 'property__property_type')

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateFavoriteSerializer
        return FavoriteSerializer

    def perform_create(self, serializer):
        # Automatically associate the favorite with the authenticated user
        instance = serializer.save(user=self.request.user)
        # Invalidate favorites cache
        cache.delete(f"user_favorites_{self.request.user.id}")
        return instance

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "Not authorized."}, status=403)
        instance.delete()
        # Invalidate favorites cache
        cache.delete(f"user_favorites_{self.request.user.id}")
        return Response(status=204)


class UserPropertyListView(generics.ListAPIView):
    """
    View to list all properties owned by the authenticated user.
    """
    serializer_class = PropertySerializer2
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        """
        This view returns a list of properties for the currently authenticated user.
        """
        return Property.objects.filter(owner=self.request.user)


class ReservationViewSet(viewsets.ModelViewSet):
    serializer_class = ReservationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            # Staff can see all reservations
            return Reservation.objects.all().select_related('property', 'user', 'property__owner')
        
        # Regular users can see their own reservations or reservations for properties they own
        return Reservation.objects.filter(
            user=user
        ).select_related('property', 'user', 'property__owner')
    
    def perform_create(self, serializer):
        property_obj = serializer.validated_data['property']
        
        # Use the property's reservation price if not provided
        reservation_price = serializer.validated_data.get('reservation_price')
        if not reservation_price and property_obj.reservation_price:
            serializer.validated_data['reservation_price'] = property_obj.reservation_price
            
        serializer.save(
            user=self.request.user,
            status='pending',
            payment_status='unpaid'
        )
    
    def update(self, request, *args, **kwargs):
        reservation = self.get_object()
        
        # Only the property owner can update the status of a reservation
        if reservation.property.owner != request.user and not request.user.is_staff:
            return Response(
                {"detail": "You do not have permission to update this reservation."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        return super().update(request, *args, **kwargs)

# API endpoint to check property availability
class PropertyAvailabilityView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    def get(self, request, *args, **kwargs):
        property_id = request.query_params.get('property_id')
        
        if not property_id:
            return Response({"error": "Missing required property_id parameter"}, status=400)
            
        # Check if property exists
        try:
            property_obj = Property.objects.get(id=property_id)
        except Property.DoesNotExist:
            return Response({"error": "Property not found"}, status=404)
            
        # Check if property is available for reservation
        if property_obj.status != 'available':
            return Response({
                "available": False,
                "property_id": property_id,
                "reason": f"Property is {property_obj.status}"
            })
            
        # Check if there are existing pending reservations
        has_pending_reservation = Reservation.objects.filter(
            property_id=property_id,
            status__in=['pending', 'confirmed']
        ).exists()
        
        return Response({
            "available": not has_pending_reservation,
            "property_id": property_id,
            "reservation_price": property_obj.reservation_price
        })