from rest_framework import serializers
from .models import Review, Requests

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['id', 'property', 'rating', 'created_at', 'updated_at']  # Exclude 'user'

    def create(self, validated_data):
        # Attach the authenticated user to the review
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['user'] = request.user
        return super().create(validated_data)

class RequestsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Requests
        fields = ['id', 'account_type', 'status', 'requester', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at', 'requester']  # Add requester here