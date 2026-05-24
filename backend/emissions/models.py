"""
EmissionRecord — the central normalized data model.

Design rationale (see MODEL.md for full discussion):

1. SOURCE-OF-TRUTH TRACKING
   Every record knows exactly which file, which row, and which batch produced it.
   is_manually_edited=True flags analyst interventions for auditors.

2. SCOPE CLASSIFICATION (GHG Protocol)
   - Scope 1: Direct emissions (fuel combustion in company-owned/controlled sources)
   - Scope 2: Indirect — purchased electricity, heat, steam
   - Scope 3: All other indirect (15 categories); we handle Cat 1 (purchased goods)
     and Cat 6 (business travel)

3. UNIT NORMALIZATION
   All activity quantities stored in SI base units before EF multiplication:
   - Volume: liters (L)
   - Energy: kWh
   - Distance: km
   - Time-based: hotel_nights

4. AUDIT TRAIL
   django-simple-history tracks every field change with who changed it and when.
   Approved records are LOCKED — the API rejects edits at the view layer.

5. MULTI-TENANCY
   organization FK on every record. Base managers always filter by org.
"""
import uuid
from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from core.models import Organization
from ingestion.models import IngestionBatch, RawRow


class EmissionFactor(models.Model):
    """
    Reference table of emission factors seeded from DEFRA 2023.
    Stored in DB so factors can be versioned and updated without code changes.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ghg_category = models.CharField(max_length=100)  # e.g. "mobile_combustion_diesel"
    description = models.CharField(max_length=255)
    activity_unit = models.CharField(max_length=50)  # unit this factor applies to
    kg_co2e_per_unit = models.DecimalField(max_digits=12, decimal_places=6)
    source = models.CharField(max_length=100)     # e.g. "DEFRA_2023"
    source_ref = models.CharField(max_length=255, blank=True)  # specific table row
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['ghg_category']

    def __str__(self):
        return f"{self.ghg_category} — {self.kg_co2e_per_unit} kgCO2e/{self.activity_unit}"


class EmissionRecord(models.Model):
    """
    One normalized, calculation-ready row of activity data.
    This is the unit of analyst review and audit submission.
    """

    # ── Scope classification ──────────────────────────────────────────────────
    class Scope(models.TextChoices):
        SCOPE_1 = 'SCOPE_1', 'Scope 1 — Direct'
        SCOPE_2 = 'SCOPE_2', 'Scope 2 — Purchased Energy'
        SCOPE_3 = 'SCOPE_3', 'Scope 3 — Value Chain'

    class SourceType(models.TextChoices):
        SAP_FUEL = 'SAP_FUEL', 'SAP Fuel'
        SAP_PROCUREMENT = 'SAP_PROCUREMENT', 'SAP Procurement'
        UTILITY_ELECTRICITY = 'UTILITY_ELECTRICITY', 'Utility Electricity'
        TRAVEL_FLIGHT = 'TRAVEL_FLIGHT', 'Business Travel — Flight'
        TRAVEL_HOTEL = 'TRAVEL_HOTEL', 'Business Travel — Hotel'
        TRAVEL_GROUND = 'TRAVEL_GROUND', 'Business Travel — Ground'

    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        FLAGGED = 'FLAGGED', 'Flagged — Needs Attention'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        LOCKED = 'LOCKED', 'Locked for Audit'

    class FlagReason(models.TextChoices):
        UNIT_MISMATCH = 'unit_mismatch', 'Unit mismatch detected'
        OUTLIER_VALUE = 'outlier_value', 'Outlier value (> 3σ from batch mean)'
        MISSING_REF = 'missing_ref', 'Missing reference data'
        DUPLICATE = 'duplicate', 'Possible duplicate row'
        DATE_GAP = 'date_gap', 'Gap in reporting period'
        OTHER = 'other', 'Other'

    # ── Identity ──────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='emission_records'
    )

    # ── Source-of-truth provenance ────────────────────────────────────────────
    batch = models.ForeignKey(
        IngestionBatch, on_delete=models.SET_NULL, null=True, related_name='records'
    )
    source_row = models.OneToOneField(
        RawRow, on_delete=models.SET_NULL, null=True, blank=True, related_name='record'
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    source_ref = models.CharField(
        max_length=255, blank=True,
        help_text="Vendor invoice #, PO number, meter ID, or trip ID from source"
    )
    source_file = models.CharField(max_length=255, blank=True)
    source_ingested_at = models.DateTimeField(auto_now_add=True)
    is_manually_edited = models.BooleanField(
        default=False,
        help_text="Set True when an analyst edits normalized values post-ingestion"
    )

    # ── GHG Scope & category ──────────────────────────────────────────────────
    scope = models.CharField(max_length=10, choices=Scope.choices)
    scope3_category = models.IntegerField(
        null=True, blank=True,
        help_text="GHG Protocol Scope 3 category 1–15; null for Scope 1 & 2"
    )
    ghg_category = models.CharField(
        max_length=100,
        help_text="Fine-grained category matching EmissionFactor.ghg_category"
    )

    # ── Activity data (normalized to SI base units) ───────────────────────────
    activity_quantity = models.DecimalField(max_digits=18, decimal_places=4)
    activity_unit = models.CharField(
        max_length=50,
        help_text="Canonical unit: liters, kWh, km, hotel_night"
    )
    activity_date = models.DateField(
        help_text="Date the activity occurred (posting date for SAP, transaction date for travel)"
    )
    reporting_period_start = models.DateField(null=True, blank=True)
    reporting_period_end = models.DateField(null=True, blank=True)

    # ── Human-readable context ────────────────────────────────────────────────
    description = models.CharField(max_length=512, blank=True)
    location = models.CharField(
        max_length=255, blank=True,
        help_text="Plant code, site name, city, or airport pair"
    )
    vendor = models.CharField(max_length=255, blank=True)

    # ── Emission calculation ──────────────────────────────────────────────────
    emission_factor = models.ForeignKey(
        EmissionFactor, on_delete=models.SET_NULL, null=True, blank=True
    )
    emission_factor_value = models.DecimalField(
        max_digits=12, decimal_places=6,
        help_text="Snapshot of EF at time of calculation (kgCO2e / activity_unit)"
    )
    emission_factor_source = models.CharField(max_length=100, blank=True)
    total_co2e_kg = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="= activity_quantity × emission_factor_value"
    )

    # ── Review workflow ───────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    flag_reason = models.CharField(
        max_length=30, choices=FlagReason.choices, blank=True
    )
    analyst_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # ── Metadata ──────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Audit trail (every field change tracked with user + timestamp) ────────
    history = HistoricalRecords()

    class Meta:
        ordering = ['-activity_date', 'source_type']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['organization', 'scope']),
            models.Index(fields=['organization', 'activity_date']),
            models.Index(fields=['batch']),
        ]

    def __str__(self):
        return (
            f"{self.source_type} | {self.activity_date} | "
            f"{self.activity_quantity} {self.activity_unit} | "
            f"{self.total_co2e_kg:.2f} kgCO2e"
        )

    def save(self, *args, **kwargs):
        # Recalculate CO2e whenever the record is saved
        if self.emission_factor_value and self.activity_quantity:
            self.total_co2e_kg = self.activity_quantity * self.emission_factor_value
        super().save(*args, **kwargs)
