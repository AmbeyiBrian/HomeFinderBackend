 # users/serializers.py
from rest_framework import serializers
from .models import CustomUser
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name',
            'last_name', 'phone_number', 'role',
            'profile_picture', 'bio', 'is_verified'
        ]
        read_only_fields = ['is_verified']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'password',
            'phone_number', 'first_name',
            'last_name', 'role','bio','id', 'profile_picture'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True}
        }

    def validate(self, data):
        return data

    def create(self, validated_data):
        user = CustomUser.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        # You can add any additional fields here if needed
        data['user'] = {
            'username': self.user.username,
            'email': self.user.email,
            'firstname': self.user.first_name,
            'lastname': self.user.last_name,
            'phonenumber': self.user.phone_number,
            'bio': self.user.bio,
            'role': self.user.role,
            'is_verified': self.user.is_verified,
            'profile_picture': self.user.profile_picture.url if self.user.profile_picture else None,
            'id':self.user.id,
        }

        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"error": "New passwords don't match"})
        return data