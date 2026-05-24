"""Ingestion serializers."""
from rest_framework import serializers
from .models import IngestionBatch, RawRow


class RawRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRow
        fields = ['id', 'row_index', 'raw_json', 'parse_status', 'parse_message']


class IngestionBatchSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = IngestionBatch
        fields = [
            'id', 'source_type', 'source_type_display', 'file_name',
            'uploaded_by', 'uploaded_by_username', 'uploaded_at',
            'status', 'status_display', 'row_count', 'error_count',
            'warning_count', 'processing_log',
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'status', 'row_count',
            'error_count', 'warning_count', 'processing_log',
        ]

    def get_uploaded_by_username(self, obj):
        return obj.uploaded_by.username if obj.uploaded_by else None


class IngestionBatchDetailSerializer(IngestionBatchSerializer):
    rows = RawRowSerializer(many=True, read_only=True)

    class Meta(IngestionBatchSerializer.Meta):
        fields = IngestionBatchSerializer.Meta.fields + ['rows']
