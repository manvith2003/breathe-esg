"""Emissions URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    path('emissions/', views.EmissionRecordListView.as_view(), name='emission_list'),
    path('emissions/<uuid:pk>/', views.EmissionRecordDetailView.as_view(), name='emission_detail'),
    path('emissions/factors/', views.EmissionFactorListView.as_view(), name='emission_factors'),
    path('dashboard/summary/', views.DashboardSummaryView.as_view(), name='dashboard_summary'),
    path('dashboard/timeline/', views.DashboardTimelineView.as_view(), name='dashboard_timeline'),
]
