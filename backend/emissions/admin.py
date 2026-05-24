"""Emissions app admin."""
from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import EmissionRecord, EmissionFactor


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ('ghg_category', 'description', 'activity_unit', 'kg_co2e_per_unit', 'source')
    list_filter = ('source',)
    search_fields = ('ghg_category', 'description')


@admin.register(EmissionRecord)
class EmissionRecordAdmin(SimpleHistoryAdmin):
    list_display = (
        'id', 'organization', 'source_type', 'scope', 'activity_date',
        'activity_quantity', 'activity_unit', 'total_co2e_kg', 'status'
    )
    list_filter = ('organization', 'scope', 'source_type', 'status')
    search_fields = ('source_ref', 'description', 'vendor', 'location')
    readonly_fields = ('id', 'source_ingested_at', 'created_at', 'updated_at', 'total_co2e_kg')
    date_hierarchy = 'activity_date'
