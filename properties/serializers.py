 
# properties/serializers.py
from rest_framework import serializers
from .models import Property, PropertyType, PropertyImage, Favorite
from users.serializers import UserSerializer

class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['property', 'image', 'is_primary','id']

class PropertyTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyType
        fields = ['id', 'name']

class PropertySerializer(serializers.ModelSerializer):
    images = PropertyImageSerializer(many=True, read_only=True)
    property_type = PropertyTypeSerializer(read_only=True)
    property_type_id = serializers.PrimaryKeyRelatedField(
        queryset=PropertyType.objects.all(),
        source='property_type',
        write_only=True
    )
    owner = UserSerializer(read_only=True)  # Add the nested serializer

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'price', 'property_type', 'listing_type',
            'property_type_id', 'bedrooms', 'bathrooms', 'square_feet',
            'address', 'city', 'state', 'zip_code',
            'latitude', 'longitude', 'status', 'owner',
            'created_at', 'updated_at', 'images', 'is_verified'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at', 'isVerified']


    def create(self, validated_data):
        # Assign the owner to the currently authenticated user
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['owner'] = request.user
        else:
            raise serializers.ValidationError("User must be authenticated to create a property.")

        return super().create(validated_data)

class FavoriteSerializer(serializers.ModelSerializer):
    property = PropertySerializer()

    class Meta:
        model = Favorite
        fields = ['id', 'property', 'created_at']


class CreateFavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ['property']