# users/views.py
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from .models import CustomUser
from .serializers import UserRegistrationSerializer,ChangePasswordSerializer
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import update_session_auth_hash

class UserViewSet(viewsets.ModelViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = UserRegistrationSerializer
    # permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        return UserRegistrationSerializer

    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'user': UserRegistrationSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.is_anonymous:
            raise AuthenticationFailed("User is not authenticated.")
        serializer = UserRegistrationSerializer(user)
        return Response(serializer.data)

class TokenObtainPairWithUserDetailsView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        tokens = serializer.validated_data
        user = serializer.user  # The authenticated user from the serializer

        user_details = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_verified': user.is_verified,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
            'id': user.id,
        }

        # Add the tokens and user details to the response
        response_data = {
            'refresh': tokens['refresh'],
            'access': tokens['access'],
            'user': user_details,
        }
        return Response(response_data, status=status.HTTP_200_OK)



from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class TokenRefreshWithUserDetailsView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        # Get the new tokens
        tokens = serializer.validated_data

        # Get the user from the access token
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(tokens['access'])
        user_id = access_token['user_id']

        # Get the user model
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Prepare user details
        user_details = {
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_verified': user.is_verified,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'profile_picture': user.profile_picture.url if user.profile_picture else None,
            'id':user.id,
        }

        # Combine tokens and user details in response
        response_data = {
            'access': tokens['access'],
            'refresh': tokens.get('refresh', request.data['refresh']),  # Keep the same refresh token
            'user': user_details,
        }

        return Response(response_data, status=status.HTTP_200_OK)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    serializer = ChangePasswordSerializer(data=request.data)
    if serializer.is_valid():
        user = request.user
        if user.check_password(serializer.validated_data['old_password']):
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            return Response(
                {"message": "Password successfully changed"},
                status=status.HTTP_200_OK
            )
        return Response(
            {"error": "Incorrect old password"},
            status=status.HTTP_400_BAD_REQUEST
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)