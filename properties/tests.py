from rest_framework import serializers
from .models import Property, PropertyType, PropertyImage, Favorite, Reservation
from users.serializers import UserSerializer

class PropertyImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyImage
        fields = ['id', 'property', 'image', 'is_primary']

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
            'id', 'title', 'description', 'price', 'reservation_price', 'property_type', 'listing_type',
            'property_type_id', 'bedrooms', 'bathrooms', 'square_feet',
            'address', 'city', 'state', 'zip_code',
            'latitude', 'longitude', 'status', 'owner',
            'created_at', 'updated_at', 'images', 'is_verified'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at', 'is_verified']

class PropertySerializer2(serializers.ModelSerializer):
    images = serializers.SerializerMethodField()  # Use a method field for custom logic
    property_type = PropertyTypeSerializer(read_only=True)
    property_type_id = serializers.PrimaryKeyRelatedField(
        queryset=PropertyType.objects.all(),
        source='property_type',
        write_only=True
    )
    owner = UserSerializer(read_only=True)

    class Meta:
        model = Property
        fields = [
            'id', 'title', 'description', 'price', 'reservation_price', 'property_type', 'listing_type',
            'property_type_id', 'bedrooms', 'bathrooms', 'square_feet',
            'address', 'city', 'state', 'zip_code',
            'latitude', 'longitude', 'status', 'owner',
            'created_at', 'updated_at', 'images', 'is_verified'
        ]
        read_only_fields = ['owner', 'created_at', 'updated_at', 'is_verified']

    def get_images(self, obj):
        """
        Custom method to return the URL of the primary image or the first image.
        """
        primary_image = obj.images.filter(is_primary=True).first()  # Get the primary image if it exists
        if primary_image:
            return primary_image.image.url  # Return the URL of the primary image
        elif obj.images.exists():
            return obj.images.first().image.url  # Return the URL of the first image
        return []  # Return an empty list if no images are available

    def create(self, validated_data):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['owner'] = request.user
        else:
            raise serializers.ValidationError("User  must be authenticated to create a property.")

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

class ReservationSerializer(serializers.ModelSerializer):
    property_details = PropertySerializer(source='property', read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = Reservation
        fields = [
            'id', 'property', 'property_details', 'user', 'user_details', 
            'reservation_price', 'booking_fee', 'total_amount',
            'status', 'payment_status', 'payment_reference',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'booking_fee', 'total_amount', 'payment_reference', 'created_at', 'updated_at']
        extra_kwargs = {
            'booking_fee': {'required': False},
            'total_amount': {'required': False}
        }

    def validate_reservation_price(self, value):
        if not value or value <= 0:
            raise serializers.ValidationError("Reservation price must be greater than 0")
        return value
    
    def create(self, validated_data):
        # Calculate booking fee and total amount based on reservation price
        reservation_price = validated_data.get('reservation_price')
        property_obj = validated_data.get('property')
        
        if reservation_price > property_obj.price:
            raise serializers.ValidationError("Reservation price cannot exceed property price")

        # Let the model's save method handle the calculations
        reservation = Reservation(**validated_data)
        reservation.save()
        return reservation