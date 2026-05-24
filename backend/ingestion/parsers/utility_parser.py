"""
Utility Electricity Parser — Green Button–style portal CSV export.

Format choice: Portal CSV (Green Button format extended with billing fields).

Rationale: Most enterprise facilities teams access electricity data via utility
web portals (EDF Energy, British Gas, E.ON, National Grid portals), not via API.
Even when an API exists (Green Button Connect My Data), the export format is CSV.
PDF bill parsing (OCR) introduces too much variability for a prototype; CSV is the
standard export an analyst would actually hand over.

Expected columns (case-insensitive, flexible ordering):
  meter_id            | Unique meter identifier
  site_name           | Human-readable site/building name
  billing_period_start| Start date of billing period (YYYY-MM-DD or DD/MM/YYYY)
  billing_period_end  | End date (exclusive — last day billed + 1, per Green Button)
  consumption_kwh     | Total kWh consumed in period; may also be in MWh
  consumption_mwh     | Alternative MWh column (will be converted to kWh)
  tariff_code         | Rate/tariff plan code (e.g. BUSINESS_FLAT, TOU_PEAK)
  is_estimated        | 'Y'/'1'/'TRUE' if reading was estimated by utility
  mpan                | UK Meter Point Administration Number (optional)
  account_ref         | Utility account reference (optional)

Normalization:
  MWh → kWh (* 1000)
  Billing periods are stored as exact start/end — not snapped to calendar months.
  This preserves the actual meter read dates which matter for audit accuracy.

Known real-world issues handled:
  - Non-calendar billing periods (e.g., 29-day cycles crossing month boundaries)
  - MWh vs kWh column variants
  - Estimated readings flagged for analyst attention
  - Missing tariff codes (common in basic utility exports)

GHG classification:
  All electricity → Scope 2, purchased_electricity_uk
  Scope 3 Cat 8 (upstream T&D losses) is not calculated in this prototype
  (documented as a deliberate tradeoff in TRADEOFFS.md).
"""
import csv
import io
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Flexible column name aliases
COLUMN_ALIASES = {
    'meter id': 'meter_id',
    'meterid': 'meter_id',
    'mpan': 'mpan',
    'site': 'site_name',
    'building': 'site_name',
    'location': 'site_name',
    'start date': 'billing_period_start',
    'period start': 'billing_period_start',
    'from': 'billing_period_start',
    'end date': 'billing_period_end',
    'period end': 'billing_period_end',
    'to': 'billing_period_end',
    'consumption (kwh)': 'consumption_kwh',
    'kwh': 'consumption_kwh',
    'energy kwh': 'consumption_kwh',
    'usage kwh': 'consumption_kwh',
    'consumption (mwh)': 'consumption_mwh',
    'mwh': 'consumption_mwh',
    'tariff': 'tariff_code',
    'rate': 'tariff_code',
    'estimated': 'is_estimated',
    'est.': 'is_estimated',
    'account': 'account_ref',
    'account number': 'account_ref',
    'account ref': 'account_ref',
}


def _normalize_header(raw: str) -> str:
    cleaned = raw.strip().lower()
    return COLUMN_ALIASES.get(cleaned, cleaned.replace(' ', '_'))


def _parse_date(raw: str) -> Optional[date]:
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y%m%d', '%d.%m.%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _is_truthy(val: str) -> bool:
    return val.strip().upper() in ('Y', 'YES', '1', 'TRUE', 'T', 'X')


def parse_utility_file(file_content: bytes, filename: str) -> List[Dict]:
    """
    Parse a utility electricity portal CSV export.

    Returns list of row dicts with raw_json, parse_status, parse_message, normalized_fields.
    """
    results = []
    try:
        text = file_content.decode('utf-8', errors='replace')
    except Exception as e:
        return [{'raw_json': {}, 'parse_status': 'ERROR',
                 'parse_message': f'Cannot decode file: {e}', 'normalized_fields': None}]

    # Skip comment/metadata lines at top (common in utility exports)
    lines = text.split('\n')
    data_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('//'):
            continue
        data_lines.append(line)
    clean_text = '\n'.join(data_lines)

    reader = csv.DictReader(io.StringIO(clean_text))

    try:
        raw_fieldnames = reader.fieldnames or []
    except Exception:
        raw_fieldnames = []

    canonical_headers = {f: _normalize_header(f) for f in raw_fieldnames}

    for row_idx, raw_row in enumerate(reader):
        row = {canonical_headers.get(k, k): v for k, v in raw_row.items() if k}
        raw_json = dict(row)

        errors = []
        warnings = []

        meter_id = row.get('meter_id', '').strip()
        site_name = row.get('site_name', '').strip()
        raw_start = row.get('billing_period_start', '').strip()
        raw_end = row.get('billing_period_end', '').strip()
        raw_kwh = row.get('consumption_kwh', '').strip()
        raw_mwh = row.get('consumption_mwh', '').strip()
        tariff_code = row.get('tariff_code', '').strip()
        is_estimated_raw = row.get('is_estimated', '').strip()
        mpan = row.get('mpan', '').strip()
        account_ref = row.get('account_ref', '').strip()

        if not meter_id and not mpan:
            warnings.append('No meter_id or MPAN — cannot link to specific meter')
        if not raw_start:
            errors.append('Missing billing_period_start')
        if not raw_end:
            errors.append('Missing billing_period_end')
        if not raw_kwh and not raw_mwh:
            errors.append('Missing consumption_kwh (and no consumption_mwh fallback)')

        # Parse dates
        period_start = _parse_date(raw_start) if raw_start else None
        period_end = _parse_date(raw_end) if raw_end else None

        if raw_start and not period_start:
            errors.append(f"Cannot parse billing_period_start '{raw_start}'")
        if raw_end and not period_end:
            errors.append(f"Cannot parse billing_period_end '{raw_end}'")

        # Parse consumption
        kwh = None
        if raw_kwh:
            try:
                kwh = Decimal(raw_kwh.replace(',', ''))
            except (InvalidOperation, ValueError):
                errors.append(f"Cannot parse consumption_kwh '{raw_kwh}'")
        elif raw_mwh:
            try:
                kwh = Decimal(raw_mwh.replace(',', '')) * Decimal('1000')
                warnings.append('Converted MWh → kWh (* 1000)')
            except (InvalidOperation, ValueError):
                errors.append(f"Cannot parse consumption_mwh '{raw_mwh}'")

        # Estimated reading flag
        is_estimated = _is_truthy(is_estimated_raw) if is_estimated_raw else False
        if is_estimated:
            warnings.append('Estimated reading — verify against actual bill')

        # Use mid-point of billing period as activity_date
        activity_date = period_start

        # Validate period order
        if period_start and period_end and period_end < period_start:
            errors.append('billing_period_end is before billing_period_start')

        # Zero or negative consumption
        if kwh is not None and kwh <= 0:
            warnings.append(f'Consumption is {kwh} kWh — check for credit/reversal')

        status = 'ERROR' if errors else ('WARNING' if warnings else 'OK')
        message = '; '.join(errors + warnings)

        normalized = None
        if not errors:
            ref_parts = [meter_id or mpan or 'METER', str(period_start), str(period_end)]
            normalized = {
                'scope': 'SCOPE_2',
                'scope3_category': None,
                'ghg_category': 'purchased_electricity_uk',
                'source_type': 'UTILITY_ELECTRICITY',
                'source_ref': '_'.join(filter(None, ref_parts)),
                'activity_quantity': kwh,
                'activity_unit': 'kWh',
                'activity_date': activity_date,
                'reporting_period_start': period_start,
                'reporting_period_end': period_end,
                'description': (
                    f"Electricity — {site_name or meter_id or mpan} "
                    f"({tariff_code or 'standard tariff'})"
                ),
                'location': site_name or mpan or meter_id,
                'vendor': account_ref or '',
                'is_estimated': is_estimated,
            }

        results.append({
            'raw_json': raw_json,
            'parse_status': status,
            'parse_message': message,
            'normalized_fields': normalized,
            'row_index': row_idx,
        })

    return results
