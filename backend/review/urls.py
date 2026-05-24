"""Review URL patterns."""
from django.urls import path
from . import views

urlpatterns = [
    path('review/<uuid:pk>/approve/', views.ApproveRecordView.as_view(), name='approve'),
    path('review/<uuid:pk>/reject/', views.RejectRecordView.as_view(), name='reject'),
    path('review/<uuid:pk>/flag/', views.FlagRecordView.as_view(), name='flag'),
    path('review/<uuid:pk>/lock/', views.LockRecordView.as_view(), name='lock'),
    path('review/<uuid:pk>/history/', views.RecordHistoryView.as_view(), name='history'),
    path('review/bulk-approve/', views.BulkApproveView.as_view(), name='bulk_approve'),
]
