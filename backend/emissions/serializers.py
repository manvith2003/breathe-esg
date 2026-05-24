"""Emissions serializers."""
from rest_framework import serializers
from .models import EmissionRecord, EmissionFactor


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = ['id', 'ghg_category', 'description', 'activity_unit',
                  'kg_co2e_per_unit', 'source', 'source_ref']


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    reviewed_by_username = serializers.SerializerMethodField()
    batch_file = serializers.SerializerMethodField()
    total_co2e_tonnes = serializers.SerializerMethodField()

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'source_type', 'source_type_display', 'source_ref', 'source_file',
            'source_ingested_at', 'is_manually_edited',
            'scope', 'scope_display', 'scope3_category', 'ghg_category',
            'activity_quantity', 'activity_unit', 'activity_date',
            'reporting_period_start', 'reporting_period_end',
            'description', 'location', 'vendor',
            'emission_factor_value', 'emission_factor_source', 'total_co2e_kg',
            'total_co2e_tonnes',
            'status', 'status_display', 'flag_reason', 'analyst_note',
            'reviewed_by', 'reviewed_by_username', 'reviewed_at',
            'batch', 'batch_file',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'source_ingested_at', 'created_at', 'updated_at',
            'total_co2e_kg', 'source_file', 'batch',
        ]

    def get_reviewed_by_username(self, obj):
        return obj.reviewed_by.username if obj.reviewed_by else None

    def get_batch_file(self, obj):
        return obj.batch.file_name if obj.batch else None

    def get_total_co2e_tonnes(self, obj):
        if obj.total_co2e_kg is not None:
            return round(float(obj.total_co2e_kg) / 1000, 6)
        return None

    def validate(self, data):
        """Prevent edits to locked/approved records except by admins."""
        instance = self.instance
        if instance and instance.status == EmissionRecord.ReviewStatus.LOCKED:
            raise serializers.ValidationError(
                "This record is locked for audit and cannot be edited."
            )
        return data

    def update(self, instance, validated_data):
        # Mark as manually edited if activity data changes
        edit_fields = {'activity_quantity', 'activity_unit', 'activity_date'}
        if any(f in validated_data for f in edit_fields):
            validated_data['is_manually_edited'] = True
        return super().update(instance, validated_data)
