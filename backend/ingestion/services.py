"""
Ingestion service — orchestrates parsing and DB record creation.

This module is the bridge between raw file uploads and normalized EmissionRecords.
It's kept separate from views so it can be called from tests or a Celery task.
"""
import logging
import statistics
from decimal import Decimal
from typing import Optional

from django.db import transaction

from emissions.models import EmissionFactor, EmissionRecord
from .models import IngestionBatch, RawRow
from .parsers import parse_sap_file, parse_utility_file, parse_travel_file

logger = logging.getLogger(__name__)

# Map ghg_category → EmissionFactor pk (cached after first run)
_EF_CACHE: dict = {}


def _get_emission_factor(ghg_category: str) -> Optional[EmissionFactor]:
    """Look up the most recent active EmissionFactor for a given category."""
    if ghg_category in _EF_CACHE:
        return _EF_CACHE[ghg_category]
    ef = EmissionFactor.objects.filter(ghg_category=ghg_category).order_by('-valid_from').first()
    if ef:
        _EF_CACHE[ghg_category] = ef
    return ef


def _detect_outliers(quantities: list[Decimal]) -> set[int]:
    """
    Return indices of rows whose quantity is > 3 standard deviations from the mean.
    Only runs when there are >= 4 rows (meaningless with fewer).
    """
    if len(quantities) < 4:
        return set()
    try:
        mean = statistics.mean(float(q) for q in quantities)
        stdev = statistics.stdev(float(q) for q in quantities)
        if stdev == 0:
            return set()
        return {
            i for i, q in enumerate(quantities)
            if abs(float(q) - mean) > 3 * stdev
        }
    except Exception:
        return set()


@transaction.atomic
def process_batch(batch: IngestionBatch, file_content: bytes) -> IngestionBatch:
    """
    Parse a file and create RawRow + EmissionRecord objects.
    Updates batch status and counters. Runs atomically.
    """
    batch.status = IngestionBatch.Status.PROCESSING
    batch.save(update_fields=['status'])

    # ── Select parser ──────────────────────────────────────────────────────
    source_type = batch.source_type
    if source_type == IngestionBatch.SourceType.SAP_FUEL:
        parsed_rows = parse_sap_file(file_content, batch.file_name)
    elif source_type == IngestionBatch.SourceType.UTILITY:
        parsed_rows = parse_utility_file(file_content, batch.file_name)
    elif source_type == IngestionBatch.SourceType.TRAVEL:
        parsed_rows = parse_travel_file(file_content, batch.file_name)
    else:
        batch.status = IngestionBatch.Status.FAILED
        batch.processing_log = f"Unknown source_type: {source_type}"
        batch.save(update_fields=['status', 'processing_log'])
        return batch

    # ── Outlier detection (run on successful rows only) ────────────────────
    ok_rows = [r for r in parsed_rows if r['normalized_fields'] is not None]
    quantities = [r['normalized_fields']['activity_quantity'] for r in ok_rows]
    outlier_indices_in_ok = _detect_outliers(quantities)
    # Map back to original row indices
    outlier_row_indices = {ok_rows[i]['row_index'] for i in outlier_indices_in_ok}

    # ── Create DB records ──────────────────────────────────────────────────
    error_count = 0
    warning_count = 0
    logs = []

    for parsed in parsed_rows:
        raw_json = parsed['raw_json']
        parse_status = parsed['parse_status']
        parse_message = parsed['parse_message']
        normalized = parsed['normalized_fields']
        row_idx = parsed.get('row_index', 0)

        if parse_status == 'ERROR':
            error_count += 1
        elif parse_status == 'WARNING':
            warning_count += 1

        if parse_status == 'ERROR':
            logs.append(f"Row {row_idx}: ERROR — {parse_message}")

        # Always create a RawRow for provenance
        raw_row = RawRow.objects.create(
            batch=batch,
            row_index=row_idx,
            raw_json=raw_json,
            parse_status=parse_status,
            parse_message=parse_message,
        )

        # Only create EmissionRecord for parseable rows
        if normalized and parse_status != 'ERROR':
            ef = _get_emission_factor(normalized['ghg_category'])

            ef_value = Decimal('0')
            ef_source = ''
            if ef:
                ef_value = ef.kg_co2e_per_unit
                ef_source = ef.source
            else:
                warning_count += 1
                logs.append(
                    f"Row {row_idx}: No emission factor found for '{normalized['ghg_category']}'"
                )

            total_co2e = normalized['activity_quantity'] * ef_value

            # Determine review status and flag reason
            review_status = EmissionRecord.ReviewStatus.PENDING
            flag_reason = ''
            if row_idx in outlier_row_indices:
                review_status = EmissionRecord.ReviewStatus.FLAGGED
                flag_reason = EmissionRecord.FlagReason.OUTLIER_VALUE
            elif parse_status == 'WARNING':
                review_status = EmissionRecord.ReviewStatus.FLAGGED
                flag_reason = EmissionRecord.FlagReason.MISSING_REF

            EmissionRecord.objects.create(
                organization=batch.organization,
                batch=batch,
                source_row=raw_row,
                source_type=normalized['source_type'],
                source_ref=normalized.get('source_ref', ''),
                source_file=batch.file_name,
                scope=normalized['scope'],
                scope3_category=normalized.get('scope3_category'),
                ghg_category=normalized['ghg_category'],
                activity_quantity=normalized['activity_quantity'],
                activity_unit=normalized['activity_unit'],
                activity_date=normalized['activity_date'],
                reporting_period_start=normalized.get('reporting_period_start'),
                reporting_period_end=normalized.get('reporting_period_end'),
                description=normalized.get('description', ''),
                location=normalized.get('location', ''),
                vendor=normalized.get('vendor', ''),
                emission_factor=ef,
                emission_factor_value=ef_value,
                emission_factor_source=ef_source,
                total_co2e_kg=total_co2e,
                status=review_status,
                flag_reason=flag_reason,
                analyst_note=parse_message if parse_status == 'WARNING' else '',
            )

    # ── Update batch status ────────────────────────────────────────────────
    batch.row_count = len(parsed_rows)
    batch.error_count = error_count
    batch.warning_count = warning_count
    batch.status = (
        IngestionBatch.Status.FAILED
        if error_count == len(parsed_rows) and len(parsed_rows) > 0
        else IngestionBatch.Status.DONE
    )
    batch.processing_log = '\n'.join(logs) if logs else 'All rows processed successfully.'
    batch.save(update_fields=['row_count', 'error_count', 'warning_count', 'status', 'processing_log'])

    return batch
