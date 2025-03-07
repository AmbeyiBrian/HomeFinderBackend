from django.db.models import Avg, Count
from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from django.core.exceptions import ValidationError
from .models import Review, Requests
from .serializers import ReviewSerializer, RequestsSerializer
from rest_framework import permissions


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get_permissions(self):
        # Override permissions for average_rating action
        if self.action == 'average_rating':
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # Attempt to save the review
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except ValidationError as e:
            # Return validation errors related to duplicate reviews
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Return any other unexpected errors
            return Response(
                {'status': 'error', 'message': 'An unexpected error occurred', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_create(self, serializer):
        # Automatically populate the user field and enforce uniqueness validation
        if Review.objects.filter(property=serializer.validated_data['property'], user=self.request.user).exists():
            raise ValidationError("You have already rated this property.")
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path=r'property/(?P<property_id>\d+)/average-rating')
    def average_rating(self, request, property_id=None):
        # Filter reviews by the property ID
        reviews = Review.objects.filter(property_id=property_id)

        # Calculate the average rating and review count for the property
        avg_data = reviews.aggregate(
            average_rating=Avg('rating'),
            review_count=Count('id')
        )

        return Response({
            'average_rating': avg_data['average_rating'] or 0,
            'review_count': avg_data['review_count']
        })


class RequestsListCreateView(generics.ListCreateAPIView):
    queryset = Requests.objects.all()
    serializer_class = RequestsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class RequestsDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Requests.objects.all()
    serializer_class = RequestsSerializer
    permission_classes = [permissions.IsAuthenticated]