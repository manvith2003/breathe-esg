"""Core serializers and auth views."""
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Organization, UserProfile


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['role', 'organization']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']


class BreatheTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT serializer that includes user info in the token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        data['user'] = UserSerializer(user).data
        return data


class BreatheTokenObtainPairView(TokenObtainPairView):
    serializer_class = BreatheTokenObtainPairSerializer
