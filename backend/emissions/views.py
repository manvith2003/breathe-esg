"""Emissions views — CRUD + dashboard."""
from datetime import datetime
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import EmissionRecord, EmissionFactor
from .serializers import EmissionRecordSerializer, EmissionFactorSerializer


class EmissionRecordListView(generics.ListAPIView):
    """GET /api/emissions/ — filterable list."""
    permission_classes = [IsAuthenticated]
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        org = self.request.user.profile.organization
        qs = EmissionRecord.objects.filter(organization=org).select_related(
            'batch', 'reviewed_by', 'emission_factor'
        )

        params = self.request.query_params

        scope = params.get('scope')
        if scope:
            qs = qs.filter(scope=scope.upper())

        review_status = params.get('status')
        if review_status:
            qs = qs.filter(status=review_status.upper())

        source_type = params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type.upper())

        batch_id = params.get('batch')
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        date_from = params.get('date_from')
        if date_from:
            try:
                qs = qs.filter(activity_date__gte=date_from)
            except (ValueError, TypeError):
                pass

        date_to = params.get('date_to')
        if date_to:
            try:
                qs = qs.filter(activity_date__lte=date_to)
            except (ValueError, TypeError):
                pass

        search = params.get('search')
        if search:
            qs = qs.filter(
                Q(description__icontains=search) |
                Q(vendor__icontains=search) |
                Q(location__icontains=search) |
                Q(source_ref__icontains=search)
            )

        return qs


class EmissionRecordDetailView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/emissions/{id}/"""
    permission_classes = [IsAuthenticated]
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        return EmissionRecord.objects.filter(
            organization=self.request.user.profile.organization
        )


class DashboardSummaryView(APIView):
    """GET /api/dashboard/summary/ — KPI data."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.profile.organization
        qs = EmissionRecord.objects.filter(organization=org)

        # Exclude rejected records from totals
        active = qs.exclude(status=EmissionRecord.ReviewStatus.REJECTED)

        total_co2e_kg = active.aggregate(total=Sum('total_co2e_kg'))['total'] or 0

        by_scope = {}
        for scope in ['SCOPE_1', 'SCOPE_2', 'SCOPE_3']:
            val = active.filter(scope=scope).aggregate(total=Sum('total_co2e_kg'))['total'] or 0
            by_scope[scope] = round(float(val) / 1000, 4)  # tCO2e

        by_status = {}
        for s in EmissionRecord.ReviewStatus.values:
            by_status[s] = qs.filter(status=s).count()

        by_source = {}
        for st in EmissionRecord.SourceType.values:
            count = active.filter(source_type=st).count()
            co2e = active.filter(source_type=st).aggregate(t=Sum('total_co2e_kg'))['t'] or 0
            by_source[st] = {'count': count, 'co2e_kg': round(float(co2e), 2)}

        return Response({
            'total_co2e_kg': round(float(total_co2e_kg), 2),
            'total_co2e_tonnes': round(float(total_co2e_kg) / 1000, 4),
            'by_scope': by_scope,
            'by_status': by_status,
            'by_source': by_source,
            'total_records': qs.count(),
            'pending_review': by_status.get('PENDING', 0),
            'flagged': by_status.get('FLAGGED', 0),
        })


class DashboardTimelineView(APIView):
    """GET /api/dashboard/timeline/ — monthly CO2e grouped by scope."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        org = request.user.profile.organization
        qs = EmissionRecord.objects.filter(
            organization=org
        ).exclude(status=EmissionRecord.ReviewStatus.REJECTED)

        # Group by year-month and scope
        from django.db.models.functions import TruncMonth
        monthly = (
            qs.annotate(month=TruncMonth('activity_date'))
            .values('month', 'scope')
            .annotate(total=Sum('total_co2e_kg'))
            .order_by('month', 'scope')
        )

        data = {}
        for row in monthly:
            month_key = row['month'].strftime('%Y-%m') if row['month'] else 'unknown'
            if month_key not in data:
                data[month_key] = {'month': month_key, 'SCOPE_1': 0, 'SCOPE_2': 0, 'SCOPE_3': 0}
            data[month_key][row['scope']] = round(float(row['total'] or 0) / 1000, 4)

        return Response(sorted(data.values(), key=lambda x: x['month']))


class EmissionFactorListView(generics.ListAPIView):
    """GET /api/emissions/factors/ — reference data."""
    permission_classes = [IsAuthenticated]
    serializer_class = EmissionFactorSerializer
    queryset = EmissionFactor.objects.all()
    pagination_class = None
