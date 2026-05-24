"""Core app URL configuration — auth endpoints."""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .serializers import BreatheTokenObtainPairView
from . import views

urlpatterns = [
    path('login/', BreatheTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', views.CurrentUserView.as_view(), name='current_user'),
]
