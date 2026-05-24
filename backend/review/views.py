"""
Review views — analyst approve/reject/flag actions.

The review workflow is the final gate before records are locked for audit.

Status transitions:
  PENDING → APPROVED (analyst signs off)
  PENDING → REJECTED (analyst rejects the row)
  PENDING → FLAGGED  (analyst flags for attention)
  FLAGGED → APPROVED
  FLAGGED → REJECTED
  APPROVED → LOCKED  (admin locks for audit submission)
  LOCKED → (immutable — no transitions allowed)

Each action is logged in the EmissionRecord's django-simple-history trail.
"""
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from emissions.models import EmissionRecord
from emissions.serializers import EmissionRecordSerializer


def _get_record(pk, org):
    try:
        return EmissionRecord.objects.get(pk=pk, organization=org)
    except EmissionRecord.DoesNotExist:
        return None


class ApproveRecordView(APIView):
    """POST /api/review/{id}/approve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = request.user.profile.organization
        record = _get_record(pk, org)
        if not record:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.status == EmissionRecord.ReviewStatus.LOCKED:
            return Response(
                {'error': 'Record is locked for audit. Cannot change status.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        record.status = EmissionRecord.ReviewStatus.APPROVED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        note = request.data.get('note', '')
        if note:
            record.analyst_note = note
        record.save()
        return Response(EmissionRecordSerializer(record).data)


class RejectRecordView(APIView):
    """POST /api/review/{id}/reject/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = request.user.profile.organization
        record = _get_record(pk, org)
        if not record:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.status == EmissionRecord.ReviewStatus.LOCKED:
            return Response(
                {'error': 'Record is locked for audit.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        record.status = EmissionRecord.ReviewStatus.REJECTED
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        note = request.data.get('note', '')
        record.analyst_note = note or record.analyst_note
        record.save()
        return Response(EmissionRecordSerializer(record).data)


class FlagRecordView(APIView):
    """POST /api/review/{id}/flag/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = request.user.profile.organization
        record = _get_record(pk, org)
        if not record:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.status == EmissionRecord.ReviewStatus.LOCKED:
            return Response(
                {'error': 'Record is locked for audit.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', EmissionRecord.FlagReason.OTHER)
        valid_reasons = [c[0] for c in EmissionRecord.FlagReason.choices]
        if reason not in valid_reasons:
            reason = EmissionRecord.FlagReason.OTHER

        record.status = EmissionRecord.ReviewStatus.FLAGGED
        record.flag_reason = reason
        note = request.data.get('note', '')
        if note:
            record.analyst_note = note
        record.save()
        return Response(EmissionRecordSerializer(record).data)


class LockRecordView(APIView):
    """POST /api/review/{id}/lock/ — Admin only."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        org = request.user.profile.organization
        record = _get_record(pk, org)
        if not record:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        if record.status != EmissionRecord.ReviewStatus.APPROVED:
            return Response(
                {'error': 'Only APPROVED records can be locked.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        record.status = EmissionRecord.ReviewStatus.LOCKED
        record.save()
        return Response(EmissionRecordSerializer(record).data)


class BulkApproveView(APIView):
    """
    POST /api/review/bulk-approve/
    Body: {"ids": ["uuid1", "uuid2", ...]}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        org = request.user.profile.organization
        ids = request.data.get('ids', [])

        if not ids:
            return Response({'error': 'No IDs provided.'}, status=status.HTTP_400_BAD_REQUEST)

        records = EmissionRecord.objects.filter(
            id__in=ids,
            organization=org,
        ).exclude(status__in=[
            EmissionRecord.ReviewStatus.LOCKED,
            EmissionRecord.ReviewStatus.REJECTED,
        ])

        count = records.count()
        records.update(
            status=EmissionRecord.ReviewStatus.APPROVED,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

        return Response({'approved': count, 'requested': len(ids)})


class RecordHistoryView(APIView):
    """GET /api/review/{id}/history/ — audit trail."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = request.user.profile.organization
        record = _get_record(pk, org)
        if not record:
            return Response({'error': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        history = record.history.all().order_by('-history_date')
        data = []
        for h in history[:50]:  # cap at 50 history entries
            data.append({
                'history_date': h.history_date,
                'history_type': h.get_history_type_display(),
                'changed_by': h.history_user.username if h.history_user else None,
                'status': h.status,
                'activity_quantity': str(h.activity_quantity),
                'analyst_note': h.analyst_note,
            })
        return Response(data)
