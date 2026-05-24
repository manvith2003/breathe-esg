"""
Ingestion models: IngestionBatch and RawRow.

IngestionBatch tracks every file upload — who uploaded it, when, the source type,
and the processing outcome. This is the source-of-truth provenance record.

RawRow stores the raw parsed JSON for each row before normalization. This lets
analysts see exactly what came in even after normalization, and lets us replay
ingestion if our parser logic changes.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from core.models import Organization


class IngestionBatch(models.Model):
    """One upload session = one batch. All EmissionRecords link back here."""

    class SourceType(models.TextChoices):
        SAP_FUEL = 'SAP_FUEL', 'SAP Fuel & Procurement'
        UTILITY = 'UTILITY', 'Utility Electricity'
        TRAVEL = 'TRAVEL', 'Corporate Travel (Concur)'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        DONE = 'DONE', 'Done'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='batches'
    )
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    file_name = models.CharField(max_length=255)
    raw_file = models.FileField(upload_to='uploads/%Y/%m/', blank=True, null=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='batches'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    warning_count = models.IntegerField(default=0)
    processing_log = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.source_type} | {self.file_name} | {self.organization.slug}"


class RawRow(models.Model):
    """
    Stores the raw parsed content of each row before normalization.
    Preserves original data for audit and replay purposes.
    """

    class ParseStatus(models.TextChoices):
        OK = 'OK', 'OK'
        WARNING = 'WARNING', 'Warning'
        ERROR = 'ERROR', 'Error'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.CASCADE, related_name='rows'
    )
    row_index = models.IntegerField()
    raw_json = models.JSONField()  # Exact key-value pairs from the source row
    parse_status = models.CharField(
        max_length=10, choices=ParseStatus.choices, default=ParseStatus.OK
    )
    parse_message = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['row_index']
        unique_together = [['batch', 'row_index']]

    def __str__(self):
        return f"Row {self.row_index} [{self.parse_status}] — batch {self.batch_id}"
