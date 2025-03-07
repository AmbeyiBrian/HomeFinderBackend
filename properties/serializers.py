from rest_framework import serializers
from decimal import Decimal
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
        
    def validate(self, data):
        if not data.get('property'):
            raise serializers.ValidationError({"property": "Property field is required"})
            
        property_obj = data['property']
        reservation_price = data.get('reservation_price')
        
        # Calculate minimum reservation price (10% of property price)
        min_reservation_price = property_obj.reservation_price or (property_obj.price * Decimal('0.1'))
        
        # If reservation_price is not provided, use the minimum
        if not reservation_price:
            data['reservation_price'] = min_reservation_price
        # Validate reservation price is within acceptable range
        elif reservation_price < min_reservation_price:
            raise serializers.ValidationError({
                "reservation_price": f"Reservation price must be at least {min_reservation_price} (10% of property price)"
            })
        elif reservation_price > property_obj.price:
            raise serializers.ValidationError({
                "reservation_price": "Reservation price cannot exceed property price"
            })
        
        # Calculate booking fee as 10% of reservation price
        data['booking_fee'] = data['reservation_price'] * Decimal('0.1')
        data['total_amount'] = data['reservation_price'] + data['booking_fee']
        
        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)