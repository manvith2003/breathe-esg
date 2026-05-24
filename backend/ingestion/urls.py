"""Ingestion URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    path('ingestion/upload/', views.UploadView.as_view(), name='upload'),
    path('ingestion/batches/', views.BatchListView.as_view(), name='batch_list'),
    path('ingestion/batches/<uuid:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),
]
