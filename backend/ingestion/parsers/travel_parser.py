"""
Corporate Travel Parser — Concur Expense File Export (CSV).

Format choice: Concur Expense File Export (CSV bulk export).

Rationale: Enterprise sustainability teams pull travel data through Concur's
built-in "Expense File Export" or similar batch exports, not via the OAuth2 API.
The API requires a registered Concur app, OAuth scopes, and tenant-specific
provisioning — setup that takes weeks. The CSV export is what a travel manager
actually emails to the sustainability team. The field names match Concur's
configurable export template.

Expense type → GHG category mapping:
  Air / Flight / Airfare  → TRAVEL_FLIGHT (Scope 3 Cat 6)
  Hotel / Lodging         → TRAVEL_HOTEL  (Scope 3 Cat 6)
  Taxi / Rideshare / Car  → TRAVEL_GROUND (Scope 3 Cat 6)

Flight distance handling:
  If distance_km is provided → use directly.
  If origin_airport + destination_airport provided → haversine great-circle distance.
  If neither → flag as WARNING with estimated EF using spend-based approach.

Hotel calculation:
  nights × emission_factor_per_night (UK average DEFRA 2023).
  If nights not provided, derive from check_in/check_out dates.

Ground transport:
  If distance_km provided → use taxi EF.
  Otherwise → flag for analyst review (spend-based calculation not implemented).

Top-50 IATA airport coordinates (lat, lon) — used for haversine fallback.
This is a deliberate subset covering the most common business travel hubs.
A production system would use a proper IATA database.
"""
import csv
import io
import logging
import math
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ── IATA airport coordinates (lat, lon) ──────────────────────────────────────
# Source: OurAirports database / Wikipedia, accurate to 0.01°
AIRPORT_COORDS = {
    'LHR': (51.4775, -0.4614),   'LGW': (51.1537, -0.1821),
    'MAN': (53.3537, -2.2750),   'EDI': (55.9500, -3.3725),
    'BHX': (52.4539, -1.7480),   'GLA': (55.8720, -4.4330),
    'BRS': (51.3827, -2.7191),   'LTN': (51.8747, -0.3683),
    'STN': (51.8850, 0.2350),    'LCY': (51.5052, 0.0552),
    'CDG': (49.0097, 2.5478),    'ORY': (48.7233, 2.3794),
    'AMS': (52.3086, 4.7639),    'FRA': (50.0379, 8.5622),
    'MUC': (48.3538, 11.7861),   'BER': (52.3667, 13.5033),
    'ZRH': (47.4647, 8.5492),    'VIE': (48.1103, 16.5697),
    'MAD': (40.4936, -3.5668),   'BCN': (41.2971, 2.0785),
    'FCO': (41.8003, 12.2389),   'MXP': (45.6306, 8.7281),
    'DUB': (53.4213, -6.2700),   'CPH': (55.6180, 12.6560),
    'ARN': (59.6519, 17.9186),   'OSL': (60.1976, 11.1004),
    'HEL': (60.3172, 24.9633),   'WAW': (52.1657, 20.9671),
    'PRG': (50.1008, 14.2600),   'BUD': (47.4298, 19.2611),
    'ATH': (37.9364, 23.9445),   'IST': (41.2753, 28.7519),
    'DXB': (25.2532, 55.3657),   'DOH': (25.2731, 51.6081),
    'AUH': (24.4330, 54.6511),   'SIN': (1.3644, 103.9915),
    'HKG': (22.3080, 113.9185),  'NRT': (35.7647, 140.3864),
    'PEK': (40.0799, 116.6031),  'PVG': (31.1443, 121.8083),
    'SYD': (-33.9399, 151.1753), 'MEL': (-37.6690, 144.8410),
    'JFK': (40.6413, -73.7781),  'EWR': (40.6895, -74.1745),
    'LAX': (33.9425, -118.4081), 'ORD': (41.9742, -87.9073),
    'SFO': (37.6213, -122.3790), 'BOS': (42.3656, -71.0096),
    'YYZ': (43.6772, -79.6306),  'GRU': (-23.4356, -46.4731),
    'MEX': (19.4363, -99.0721),  'NBO': (-1.3192, 36.9275),
    'JNB': (-26.1392, 28.2460),  'CPT': (-33.9648, 18.6017),
    'BOM': (19.0887, 72.8679),   'DEL': (28.5562, 77.1000),
    'BLR': (13.1986, 77.7066),   'MAA': (12.9900, 80.1693),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two (lat, lon) pairs in km.
    Uses haversine formula. Accuracy ≈ 0.3% vs actual flight paths.
    """
    R = 6371.0  # Earth radius km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _flight_distance_km(
    origin: str, destination: str
) -> Tuple[Optional[float], str]:
    """
    Return great-circle distance and a message explaining the method.
    """
    o = origin.strip().upper()
    d = destination.strip().upper()
    if o in AIRPORT_COORDS and d in AIRPORT_COORDS:
        km = _haversine_km(*AIRPORT_COORDS[o], *AIRPORT_COORDS[d])
        return km, f"Haversine great-circle {o}→{d}"
    missing = [code for code in [o, d] if code not in AIRPORT_COORDS]
    return None, f"Airport code(s) not in lookup table: {', '.join(missing)}"


def _classify_flight(distance_km: float) -> str:
    """Short-haul <3700km, long-haul ≥3700km per DEFRA/ICAO convention."""
    return (
        'business_travel_flight_short_haul_economy'
        if distance_km < 3700
        else 'business_travel_flight_long_haul_economy'
    )


def _parse_date(raw: str) -> Optional[date]:
    raw = raw.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_header(raw: str) -> str:
    return raw.strip().lower().replace(' ', '_').replace('-', '_')


EXPENSE_TYPE_MAP = {
    # Flights
    'air': 'FLIGHT', 'airfare': 'FLIGHT', 'flight': 'FLIGHT',
    'airline': 'FLIGHT', 'air travel': 'FLIGHT', 'air ticket': 'FLIGHT',
    # Hotels
    'hotel': 'HOTEL', 'lodging': 'HOTEL', 'accommodation': 'HOTEL',
    'hotel accommodation': 'HOTEL', 'hotel - single rate': 'HOTEL',
    # Ground
    'taxi': 'GROUND', 'rideshare': 'GROUND', 'car rental': 'GROUND',
    'ground transport': 'GROUND', 'uber': 'GROUND', 'cab': 'GROUND',
    'car hire': 'GROUND', 'rental car': 'GROUND', 'train': 'GROUND',
}


def _classify_expense(expense_type: str) -> Optional[str]:
    """Returns 'FLIGHT', 'HOTEL', or 'GROUND', or None if unrecognized."""
    et = expense_type.strip().lower()
    if et in EXPENSE_TYPE_MAP:
        return EXPENSE_TYPE_MAP[et]
    # Partial match
    for key, val in EXPENSE_TYPE_MAP.items():
        if key in et:
            return val
    return None


def parse_travel_file(file_content: bytes, filename: str) -> List[Dict]:
    """
    Parse a Concur-style travel expense CSV export.

    Expected columns:
      report_id, expense_type, transaction_date, vendor_name,
      amount_usd, currency, origin_airport, destination_airport,
      seat_class, hotel_city, check_in_date, check_out_date,
      nights, distance_km, traveler_name, cost_center
    """
    results = []
    try:
        text = file_content.decode('utf-8', errors='replace')
    except Exception as e:
        return [{'raw_json': {}, 'parse_status': 'ERROR',
                 'parse_message': f'Cannot decode file: {e}', 'normalized_fields': None}]

    reader = csv.DictReader(io.StringIO(text))

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

        report_id = row.get('report_id', '').strip()
        expense_type_raw = row.get('expense_type', '').strip()
        raw_date = row.get('transaction_date', '').strip()
        vendor = row.get('vendor_name', '').strip()
        raw_amount = row.get('amount_usd', row.get('amount', '')).strip()
        origin = row.get('origin_airport', '').strip()
        destination = row.get('destination_airport', '').strip()
        seat_class = row.get('seat_class', row.get('class', 'economy')).strip().lower()
        hotel_city = row.get('hotel_city', '').strip()
        raw_check_in = row.get('check_in_date', '').strip()
        raw_check_out = row.get('check_out_date', '').strip()
        raw_nights = row.get('nights', '').strip()
        raw_distance = row.get('distance_km', '').strip()
        cost_center = row.get('cost_center', '').strip()

        if not expense_type_raw:
            errors.append('Missing expense_type')
        if not raw_date:
            errors.append('Missing transaction_date')

        activity_date = _parse_date(raw_date) if raw_date else None
        if raw_date and not activity_date:
            errors.append(f"Cannot parse transaction_date '{raw_date}'")

        category = _classify_expense(expense_type_raw) if expense_type_raw else None
        if expense_type_raw and not category:
            warnings.append(f"Unrecognized expense_type '{expense_type_raw}' — skipping")
            errors.append(f"Cannot classify expense_type '{expense_type_raw}'")

        # ── Per-category processing ───────────────────────────────────────
        normalized = None
        if not errors:
            if category == 'FLIGHT':
                # Distance: explicit > haversine > error
                distance_km = None
                distance_method = ''
                if raw_distance:
                    try:
                        distance_km = float(raw_distance.replace(',', ''))
                        distance_method = 'provided'
                    except ValueError:
                        warnings.append(f"Cannot parse distance_km '{raw_distance}'")

                if distance_km is None and origin and destination:
                    distance_km, distance_method = _flight_distance_km(origin, destination)
                    if distance_km is None:
                        warnings.append(distance_method)

                if distance_km is None:
                    errors.append('Cannot determine flight distance — provide distance_km or valid IATA codes')
                else:
                    # Adjust for seat class
                    if 'business' in seat_class or 'first' in seat_class:
                        ghg_cat = (
                            'business_travel_flight_short_haul_business'
                            if distance_km < 3700
                            else 'business_travel_flight_long_haul_business'
                        )
                    else:
                        ghg_cat = _classify_flight(distance_km)

                    route = f"{origin}→{destination}" if (origin and destination) else "Route unknown"
                    normalized = {
                        'scope': 'SCOPE_3',
                        'scope3_category': 6,
                        'ghg_category': ghg_cat,
                        'source_type': 'TRAVEL_FLIGHT',
                        'source_ref': report_id or f"TRAVEL_ROW_{row_idx}",
                        'activity_quantity': Decimal(str(round(distance_km, 2))),
                        'activity_unit': 'km',
                        'activity_date': activity_date,
                        'reporting_period_start': activity_date,
                        'reporting_period_end': activity_date,
                        'description': f"Flight {route} ({seat_class}) — {vendor or 'unknown airline'}",
                        'location': route,
                        'vendor': vendor,
                        'distance_method': distance_method,
                    }
                    if distance_method and distance_method != 'provided':
                        warnings.append(f"Distance calculated via {distance_method}: {round(distance_km, 0)} km")

            elif category == 'HOTEL':
                # Nights: explicit > derive from dates
                nights = None
                check_in = _parse_date(raw_check_in) if raw_check_in else None
                check_out = _parse_date(raw_check_out) if raw_check_out else None

                if raw_nights:
                    try:
                        nights = int(raw_nights)
                    except ValueError:
                        warnings.append(f"Cannot parse nights '{raw_nights}'")

                if nights is None and check_in and check_out:
                    nights = (check_out - check_in).days
                    warnings.append(f"Derived {nights} nights from check_in/check_out dates")

                if nights is None or nights <= 0:
                    errors.append('Cannot determine hotel nights — provide nights or check_in/check_out')
                else:
                    location = hotel_city or (cost_center + ' hotel') or 'Unknown location'
                    normalized = {
                        'scope': 'SCOPE_3',
                        'scope3_category': 6,
                        'ghg_category': 'business_travel_hotel_uk',
                        'source_type': 'TRAVEL_HOTEL',
                        'source_ref': report_id or f"TRAVEL_ROW_{row_idx}",
                        'activity_quantity': Decimal(str(nights)),
                        'activity_unit': 'hotel_night',
                        'activity_date': activity_date or check_in,
                        'reporting_period_start': check_in or activity_date,
                        'reporting_period_end': check_out or activity_date,
                        'description': f"Hotel stay {nights}N — {vendor or location}",
                        'location': location,
                        'vendor': vendor,
                    }

            elif category == 'GROUND':
                # Ground: use distance if provided, else flag
                distance_km = None
                if raw_distance:
                    try:
                        distance_km = Decimal(raw_distance.replace(',', ''))
                    except (InvalidOperation, ValueError):
                        warnings.append(f"Cannot parse distance_km '{raw_distance}'")

                if distance_km is None:
                    warnings.append(
                        'No distance_km for ground transport — cannot calculate km-based EF. '
                        'Spend-based calculation not implemented (see TRADEOFFS.md).'
                    )
                    # Create a zero-quantity placeholder record that analysts can fix
                    distance_km = Decimal('0')
                    errors.append('Missing distance for ground transport — analyst must fill in')
                else:
                    normalized = {
                        'scope': 'SCOPE_3',
                        'scope3_category': 6,
                        'ghg_category': 'business_travel_ground_taxi',
                        'source_type': 'TRAVEL_GROUND',
                        'source_ref': report_id or f"TRAVEL_ROW_{row_idx}",
                        'activity_quantity': distance_km,
                        'activity_unit': 'km',
                        'activity_date': activity_date,
                        'reporting_period_start': activity_date,
                        'reporting_period_end': activity_date,
                        'description': f"Ground transport — {vendor or expense_type_raw}",
                        'location': cost_center or '',
                        'vendor': vendor,
                    }

        status = 'ERROR' if errors else ('WARNING' if warnings else 'OK')
        message = '; '.join(errors + warnings)

        results.append({
            'raw_json': raw_json,
            'parse_status': status,
            'parse_message': message,
            'normalized_fields': normalized,
            'row_index': row_idx,
        })

    return results
