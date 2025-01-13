from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError
from .models import PropertyType, PropertyImage, Property
from .serializers import PropertyTypeSerializer, PropertyImageSerializer, PropertySerializer, CreateFavoriteSerializer


class PropertyListView(generics.ListCreateAPIView):
    serializer_class = PropertySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['listing_type', 'bedrooms', 'bathrooms', 'property_type__name']
    permission_classes = [IsAuthenticatedOrReadOnly]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        queryset = Property.objects.all()

        # Get query parameters
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        city = self.request.query_params.get('city')
        property_type = self.request.query_params.get('property_type')  # Expecting 'name' here
        listing_type = self.request.query_params.get('listing_type')
        owner = self.request.query_params.get('owner')  # New parameter for owner

        try:
            if min_price:
                queryset = queryset.filter(price__gte=float(min_price))
            if max_price:
                queryset = queryset.filter(price__lte=float(max_price))
            if city:
                queryset = queryset.filter(city__icontains=city)
            if property_type:
                queryset = queryset.filter(property_type__name__icontains=property_type)  # Match name
            if listing_type:
                queryset = queryset.filter(listing_type__icontains=listing_type)
            if owner:
                queryset = queryset.filter(owner_id=owner)  # Filter by owner ID
        except ValueError as e:
            # Handle invalid numeric values gracefully
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
    queryset = Property.objects.all()
    serializer_class = PropertySerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    authentication_classes = [JWTAuthentication]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Ensure only owner can update
        if instance.owner != request.user:
            return Response(
                {"detail": "You do not have permission to update this property."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        # Ensure only owner can delete
        if instance.owner != request.user:
            return Response(
                {"detail": "You do not have permission to delete this property."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class PropertyTypeListView(generics.ListAPIView):
    """
    API to fetch all property types.
    """
    queryset = PropertyType.objects.all()
    serializer_class = PropertyTypeSerializer
    authentication_classes = [JWTAuthentication]
    # No permission_classes needed as this is read-only


class PropertyImageCreateView(generics.CreateAPIView):
    queryset = PropertyImage.objects.all()
    serializer_class = PropertyImageSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def perform_create(self, serializer):
        try:
            # Save the image with the current user
            serializer.save()
            print(serializer.data)
        except Exception as e:
            raise ValidationError(f"Error creating property image: {str(e)}")

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except ValidationError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PropertyImageDeleteView(generics.DestroyAPIView):
    """
    API to delete a property image.
    """
    queryset = PropertyImage.objects.all()
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            instance.delete()
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

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Favorite, Property
from .serializers import FavoriteSerializer

from rest_framework import status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateFavoriteSerializer
        return FavoriteSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user != request.user:
            return Response({"detail": "Not authorized."}, status=403)
        instance.delete()
        return Response(status=204)

