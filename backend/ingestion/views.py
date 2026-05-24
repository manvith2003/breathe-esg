"""Ingestion views — file upload and batch management."""
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import IngestionBatch
from .serializers import IngestionBatchSerializer, IngestionBatchDetailSerializer
from .services import process_batch


class UploadView(APIView):
    """
    POST /api/ingestion/upload/
    Accepts multipart form with:
      - file: the data file
      - source_type: SAP_FUEL | UTILITY | TRAVEL
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        user = request.user
        try:
            profile = user.profile
        except Exception:
            return Response(
                {'error': 'User has no organization profile. Contact an admin.'},
                status=status.HTTP_403_FORBIDDEN
            )

        source_type = request.data.get('source_type', '').upper()
        valid_types = [c[0] for c in IngestionBatch.SourceType.choices]
        if source_type not in valid_types:
            return Response(
                {'error': f"Invalid source_type. Must be one of: {valid_types}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create batch record
        batch = IngestionBatch.objects.create(
            organization=profile.organization,
            source_type=source_type,
            file_name=uploaded_file.name,
            raw_file=uploaded_file,
            uploaded_by=user,
        )

        # Read file content for parsing (stored in media, also passed in-memory)
        uploaded_file.seek(0)
        file_content = uploaded_file.read()

        # Process synchronously for prototype
        # In production, dispatch to Celery task
        try:
            batch = process_batch(batch, file_content)
        except Exception as e:
            batch.status = IngestionBatch.Status.FAILED
            batch.processing_log = str(e)
            batch.save(update_fields=['status', 'processing_log'])

        return Response(
            IngestionBatchSerializer(batch).data,
            status=status.HTTP_201_CREATED
        )


class BatchListView(generics.ListAPIView):
    """GET /api/ingestion/batches/ — list all batches for the user's org."""
    permission_classes = [IsAuthenticated]
    serializer_class = IngestionBatchSerializer

    def get_queryset(self):
        org = self.request.user.profile.organization
        qs = IngestionBatch.objects.filter(organization=org)
        source_type = self.request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type.upper())
        return qs


class BatchDetailView(generics.RetrieveAPIView):
    """GET /api/ingestion/batches/{id}/ — batch detail with rows."""
    permission_classes = [IsAuthenticated]
    serializer_class = IngestionBatchDetailSerializer

    def get_queryset(self):
        return IngestionBatch.objects.filter(
            organization=self.request.user.profile.organization
        ).prefetch_related('rows')
