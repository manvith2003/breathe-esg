"""
SAP Fuel & Procurement parser.

Format choice: Pipe-delimited (|) flat file, custom ABAP extract style.

Rationale: Real SAP systems rarely expose clean APIs directly. The most common
real-world integration pattern for external systems is a Z-program (custom ABAP)
that queries EKKO/EKPO (purchasing docs) and MSEG (material movements) and writes
a pipe-delimited file. This is what a facilities or sustainability team actually
receives via SFTP or email. Native IDoc fixed-width files require EDI middleware
(SAP PI/PO) to parse — overkill for this integration layer.

Column mapping (supports German aliases common in older SAP configs):
  English         | German alias    | Meaning
  ----------------|-----------------|------------------
  PO_NUMBER       | Bestellnummer   | Purchase order ID
  MATERIAL_ID     | Materialnummer  | Material/fuel type code
  MATERIAL_DESC   | Materialtext    | Human-readable name
  QUANTITY        | Menge           | Amount consumed
  UNIT            | Einheit         | Unit of measure (L, GAL, KG, M3, KWH)
  PLANT_CODE      | Werk            | Plant/site identifier
  STORAGE_LOC     | Lagerort        | Storage location within plant
  VENDOR_ID       | Lieferant       | Vendor/supplier code
  POSTING_DATE    | Buchungsdatum   | GL posting date (DD.MM.YYYY or YYYY-MM-DD)
  DOCUMENT_TYPE   | Belegart        | PO type (NB=standard, ZFUEL=fuel specific)
  COST_CENTER     | Kostenstelle    | Cost center for allocation
  CURRENCY        | Währung         | Transaction currency

Unit normalization:
  L, LITRE, LITER, LTR -> liters (no conversion)
  GAL, GALLON          -> liters (* 3.78541)
  M3                   -> liters (* 1000) [for LPG/gas volume]
  KG                   -> kg (mass — used for coal, biomass; kept as-is)
  KWH, KWHR            -> kWh (for natural gas billing in energy units)

GHG classification:
  DIESEL               -> Scope 1, mobile_combustion_diesel
  PETROL, BENZIN       -> Scope 1, mobile_combustion_petrol
  NATURAL_GAS, ERDGAS  -> Scope 1, stationary_combustion_natural_gas
  LPG, PROPAN          -> Scope 1, mobile_combustion_lpg
  Everything else      -> Scope 3 Cat 1 (purchased goods), flagged for review
"""
import csv
import io
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple, Optional
from emissions.models import EmissionFactor

logger = logging.getLogger(__name__)

# ── German → English column alias map ────────────────────────────────────────
GERMAN_ALIASES = {
    'bestellnummer': 'PO_NUMBER',
    'materialnummer': 'MATERIAL_ID',
    'materialtext': 'MATERIAL_DESC',
    'menge': 'QUANTITY',
    'einheit': 'UNIT',
    'werk': 'PLANT_CODE',
    'lagerort': 'STORAGE_LOC',
    'lieferant': 'VENDOR_ID',
    'buchungsdatum': 'POSTING_DATE',
    'belegart': 'DOCUMENT_TYPE',
    'kostenstelle': 'COST_CENTER',
    'währung': 'CURRENCY',
    'wahrung': 'CURRENCY',
}

# ── Hardcoded plant code → site name lookup ───────────────────────────────────
PLANT_LOOKUP = {
    'PLANT_001': 'London Headquarters',
    'PLANT_002': 'Manchester Depot',
    'PLANT_003': 'Birmingham Distribution Centre',
    'PLANT_004': 'Leeds Warehouse',
    'PLANT_005': 'Glasgow Operations',
    'P001': 'London Headquarters',
    'P002': 'Manchester Depot',
    'P003': 'Birmingham Distribution Centre',
    'UK01': 'London Site A',
    'UK02': 'London Site B',
    'DE01': 'Berlin Office',
    'DE02': 'Munich Facility',
}

# ── Material → fuel type classification ──────────────────────────────────────
FUEL_CLASSIFICATIONS = {
    'diesel': ('SCOPE_1', 'mobile_combustion_diesel', 'liters'),
    'gasoil': ('SCOPE_1', 'mobile_combustion_diesel', 'liters'),
    'petrol': ('SCOPE_1', 'mobile_combustion_petrol', 'liters'),
    'benzin': ('SCOPE_1', 'mobile_combustion_petrol', 'liters'),
    'gasoline': ('SCOPE_1', 'mobile_combustion_petrol', 'liters'),
    'natural_gas': ('SCOPE_1', 'stationary_combustion_natural_gas', 'kWh'),
    'erdgas': ('SCOPE_1', 'stationary_combustion_natural_gas', 'kWh'),
    'natural gas': ('SCOPE_1', 'stationary_combustion_natural_gas', 'kWh'),
    'lpg': ('SCOPE_1', 'mobile_combustion_lpg', 'liters'),
    'propan': ('SCOPE_1', 'mobile_combustion_lpg', 'liters'),
    'propane': ('SCOPE_1', 'mobile_combustion_lpg', 'liters'),
}

# ── Unit conversion to canonical SI ──────────────────────────────────────────
UNIT_CONVERSIONS = {
    'l': ('liters', Decimal('1')),
    'liter': ('liters', Decimal('1')),
    'litre': ('liters', Decimal('1')),
    'ltr': ('liters', Decimal('1')),
    'liters': ('liters', Decimal('1')),
    'litres': ('liters', Decimal('1')),
    'gal': ('liters', Decimal('3.78541')),
    'gallon': ('liters', Decimal('3.78541')),
    'gallons': ('liters', Decimal('3.78541')),
    'usgal': ('liters', Decimal('3.78541')),
    'm3': ('liters', Decimal('1000')),
    'kg': ('kg', Decimal('1')),
    'kwh': ('kWh', Decimal('1')),
    'kwhr': ('kWh', Decimal('1')),
    'mwh': ('kWh', Decimal('1000')),
}


def _normalize_header(raw: str) -> str:
    """Lower-strip a header and map German alias to English canonical name."""
    cleaned = raw.strip().lower().replace(' ', '_').replace('-', '_')
    return GERMAN_ALIASES.get(cleaned, raw.strip().upper())


def _parse_date(raw: str) -> Optional[date]:
    """Parse DD.MM.YYYY (SAP default) or YYYY-MM-DD or DD/MM/YYYY."""
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_quantity_unit(
    raw_qty: str, raw_unit: str
) -> Tuple[Optional[Decimal], str, str]:
    """
    Convert quantity and unit to canonical form.
    Returns (normalized_quantity, canonical_unit, warning_message)
    """
    unit_key = raw_unit.strip().lower()
    if unit_key not in UNIT_CONVERSIONS:
        return None, raw_unit, f"Unknown unit '{raw_unit}'"
    canonical_unit, factor = UNIT_CONVERSIONS[unit_key]
    try:
        qty = Decimal(raw_qty.strip().replace(',', '.')) * factor
        return qty, canonical_unit, ''
    except (InvalidOperation, ValueError) as e:
        return None, raw_unit, f"Cannot parse quantity '{raw_qty}': {e}"


def _classify_material(material_id: str, material_desc: str) -> Tuple[str, str, str]:
    """
    Returns (scope, ghg_category, canonical_unit).
    Falls back to Scope 3 / purchased_goods for unrecognized materials.
    """
    search = (material_id + ' ' + material_desc).lower()
    for keyword, classification in FUEL_CLASSIFICATIONS.items():
        if keyword in search:
            return classification
    # Not a recognised fuel — treat as purchased goods (Scope 3 Cat 1)
    return ('SCOPE_3', 'purchased_goods', 'kg')


def parse_sap_file(
    file_content: bytes, filename: str
) -> List[Dict]:
    """
    Parse a SAP pipe-delimited flat file export.

    Returns a list of dicts with keys:
      raw_json, parse_status, parse_message, normalized_fields
    """
    results = []
    try:
        text = file_content.decode('utf-8', errors='replace')
    except Exception as e:
        return [{'raw_json': {}, 'parse_status': 'ERROR',
                 'parse_message': f'Cannot decode file: {e}', 'normalized_fields': None}]

    # Auto-detect delimiter — prefer pipe, fall back to comma
    first_line = text.split('\n')[0] if text else ''
    delimiter = '|' if '|' in first_line else ','

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    # Remap headers
    try:
        raw_fieldnames = reader.fieldnames or []
    except Exception:
        raw_fieldnames = []

    canonical_headers = {f: _normalize_header(f) for f in raw_fieldnames}

    for row_idx, raw_row in enumerate(reader):
        # Remap row keys to canonical names
        row = {canonical_headers.get(k, k): v for k, v in raw_row.items() if k}
        raw_json = dict(row)

        warnings = []
        errors = []

        # ── Required fields ───────────────────────────────────────────────
        material_id = row.get('MATERIAL_ID', '').strip()
        material_desc = row.get('MATERIAL_DESC', '').strip()
        raw_qty = row.get('QUANTITY', '').strip()
        raw_unit = row.get('UNIT', '').strip()
        raw_date = row.get('POSTING_DATE', '').strip()
        plant_code = row.get('PLANT_CODE', '').strip()
        po_number = row.get('PO_NUMBER', '').strip()
        vendor_id = row.get('VENDOR_ID', '').strip()

        if not raw_qty:
            errors.append('Missing QUANTITY')
        if not raw_unit:
            errors.append('Missing UNIT')
        if not raw_date:
            errors.append('Missing POSTING_DATE')

        # ── Date parsing ──────────────────────────────────────────────────
        activity_date = _parse_date(raw_date) if raw_date else None
        if raw_date and not activity_date:
            errors.append(f"Cannot parse date '{raw_date}'")

        # ── Unit normalization ────────────────────────────────────────────
        norm_qty, norm_unit, unit_warn = _normalize_quantity_unit(raw_qty, raw_unit)
        if unit_warn:
            if norm_qty is None:
                errors.append(unit_warn)
            else:
                warnings.append(unit_warn)

        # ── Classification ────────────────────────────────────────────────
        scope, ghg_category, expected_unit = _classify_material(material_id, material_desc)

        # Override unit if classification expects a different base unit
        # (e.g. natural gas in M3 → kWh requires density conversion which we skip;
        #  instead we keep kWh if supplied directly)
        if norm_unit and expected_unit and norm_unit != expected_unit:
            if ghg_category == 'stationary_combustion_natural_gas' and norm_unit == 'liters':
                # M3 of gas → approximate kWh using 10.55 kWh/m3 (gross CV, UK avg)
                norm_qty = norm_qty / Decimal('1000') * Decimal('10.55')
                norm_unit = 'kWh'
                warnings.append("Converted m3 natural gas to kWh using 10.55 kWh/m3 (UK gross CV)")

        # ── Plant lookup ──────────────────────────────────────────────────
        site_name = PLANT_LOOKUP.get(plant_code, plant_code)

        if not material_id and not material_desc:
            warnings.append('No material identifier — classification may be incorrect')

        # ── Scope 3 flag ──────────────────────────────────────────────────
        scope3_category = None
        if scope == 'SCOPE_3':
            scope3_category = 1  # Purchased goods and services

        # ── Assemble result ───────────────────────────────────────────────
        status = 'ERROR' if errors else ('WARNING' if warnings else 'OK')
        message = '; '.join(errors + warnings)

        normalized = None
        if not errors:
            normalized = {
                'scope': scope,
                'scope3_category': scope3_category,
                'ghg_category': ghg_category,
                'source_type': 'SAP_FUEL' if scope == 'SCOPE_1' else 'SAP_PROCUREMENT',
                'source_ref': po_number or f"ROW_{row_idx}",
                'activity_quantity': norm_qty,
                'activity_unit': norm_unit,
                'activity_date': activity_date,
                'reporting_period_start': activity_date,
                'reporting_period_end': activity_date,
                'description': f"{material_desc or material_id} — {site_name}",
                'location': site_name,
                'vendor': vendor_id,
            }

        results.append({
            'raw_json': raw_json,
            'parse_status': status,
            'parse_message': message,
            'normalized_fields': normalized,
            'row_index': row_idx,
        })

    return results
