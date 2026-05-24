# MODEL.md — Data Model Documentation

## Overview

BreatheESG's data model is designed around three non-negotiable requirements:

1. **Source-of-truth tracking** — every normalized record must be traceable back to the exact row in the exact file that produced it
2. **Multi-tenancy** — multiple client organizations share the same database without data leakage
3. **Audit readiness** — every field change is logged with who made it and when, and approved records are immutable

---

## Multi-Tenancy Strategy

**Approach chosen: Shared Database, Shared Schema with `organization` FK on every data record.**

Every `IngestionBatch`, `RawRow`, and `EmissionRecord` carries an `organization` FK. All view-layer querysets are filtered `filter(organization=request.user.profile.organization)` before returning any data. This is enforced at the base queryset level, not in individual business logic.

**Why not `django-tenants` (separate schemas)?**
For a prototype with 1–3 test tenants, the operational overhead of schema-switching middleware is not justified. The shared-schema approach with strict FK filtering achieves the same logical isolation. A production migration to `django-tenants` would be a straightforward schema change — the FK is already on every model.

**Security guarantee:** A user authenticated as Org A cannot retrieve Org B data through any API endpoint, because all querysets start with `filter(organization=request.user.profile.organization)`.

---

## Models

### `Organization` (core app)
```
id           UUID PK
name         str (unique)
slug         str (unique) — used in URLs and references
created_at   datetime
updated_at   datetime
```
The top-level tenant. Every data record belongs to exactly one Organization.

---

### `UserProfile` (core app)
```
user         OneToOne → Django User
organization FK → Organization
role         ENUM(ANALYST, ADMIN)
created_at   datetime
```
Extends Django's built-in User. Analysts can review/approve/flag. Admins can lock records. Profile creation requires explicit organization assignment — no auto-creation on User save, to prevent orphaned profiles.

---

### `IngestionBatch` (ingestion app)
```
id             UUID PK
organization   FK → Organization
source_type    ENUM(SAP_FUEL, UTILITY, TRAVEL)
file_name      str
raw_file       FileField — stored in /media/uploads/YYYY/MM/
uploaded_by    FK → User (SET_NULL on delete)
uploaded_at    datetime (auto)
status         ENUM(PENDING, PROCESSING, DONE, FAILED)
row_count      int
error_count    int
warning_count  int
processing_log text — human-readable per-row error summary
```

A batch represents one file upload session. Its status transitions: `PENDING → PROCESSING → DONE | FAILED`. Every `EmissionRecord` links back to its batch, providing provenance to the file level.

---

### `RawRow` (ingestion app)
```
id             UUID PK
batch          FK → IngestionBatch
row_index      int (0-based)
raw_json       JSONField — exact key:value pairs from the source row
parse_status   ENUM(OK, WARNING, ERROR)
parse_message  text — human-readable parse issue description
```

**Why store raw rows?**
- Audit requirement: auditors need to see the unmodified source data alongside normalized values
- Replay: if parser logic changes (e.g., a new unit type discovered), batches can be re-parsed without re-uploading the file
- Analyst transparency: the "Raw Data" tab in the review UI shows the original row JSON

Unique constraint on `(batch, row_index)` prevents duplicates on re-runs.

---

### `EmissionFactor` (emissions app)
```
id               UUID PK
ghg_category     str — matches the fine-grained category string used by parsers
description      str
activity_unit    str — the unit this EF applies to (liters, kWh, km, hotel_night)
kg_co2e_per_unit Decimal(12,6)
source           str — e.g. "DEFRA_2023"
source_ref       str — specific table and row in the source document
valid_from       date
valid_to         date
```

Emission factors are stored in the database (not hardcoded) so they can be updated independently of code. The `valid_from / valid_to` fields support multi-year reporting where different factors apply to different periods. Seeded from `emissions/fixtures/emission_factors.json` using `loaddata`.

**Source: UK DEFRA Greenhouse Gas Reporting — Conversion Factors 2023**

---

### `EmissionRecord` (emissions app) — *The central model*

This is the unit of analyst review, audit submission, and carbon accounting.

#### Identity
```
id               UUID PK
organization     FK → Organization
```

#### Source-of-Truth Provenance
```
batch            FK → IngestionBatch (SET_NULL — record survives batch deletion)
source_row       OneToOne → RawRow (SET_NULL — record survives row deletion)
source_type      ENUM(SAP_FUEL, SAP_PROCUREMENT, UTILITY_ELECTRICITY,
                      TRAVEL_FLIGHT, TRAVEL_HOTEL, TRAVEL_GROUND)
source_ref       str — vendor invoice #, PO number, meter ID, or trip ID
source_file      str — original filename (snapshot, survives file deletion)
source_ingested_at datetime — when this record was created
is_manually_edited bool — set True when analyst edits normalized values
```

`is_manually_edited` is critical for auditors: it flags records where human judgment overrode the parsed value. The specific change is captured in the history trail.

#### GHG Scope & Category
```
scope            ENUM(SCOPE_1, SCOPE_2, SCOPE_3)
scope3_category  int (1–15, nullable for Scope 1 & 2)
ghg_category     str — matches EmissionFactor.ghg_category
```

Scope classification follows the GHG Protocol Corporate Standard:
- **Scope 1:** Direct emissions from owned/controlled sources (fuel combustion)
- **Scope 2:** Indirect from purchased electricity (location-based method)
- **Scope 3:** All other indirect; our categories:
  - Category 1: Purchased goods (unrecognized SAP materials)
  - Category 6: Business travel (flights, hotels, ground transport)

#### Activity Data (normalized to SI base units)
```
activity_quantity       Decimal(18,4) — in canonical unit
activity_unit           str — "liters", "kWh", "km", "hotel_night"
activity_date           date — posting/transaction date
reporting_period_start  date — start of the period this covers
reporting_period_end    date — end of the period (may differ from activity_date for utility billing)
```

**Unit normalization rationale:** Storing in canonical units (not source units) means the emission calculation is always `activity_quantity × emission_factor_value` with no further conversion. The original unit is preserved in `RawRow.raw_json` for audit reference.

**Why separate `activity_date` from `reporting_period_start/end`?**
Utility electricity has billing periods that don't align with calendar dates. A reading from 2024-01-29 to 2024-02-26 has `activity_date = 2024-01-29` (the billing start) but the emissions span both months. The period fields allow accurate period-based reporting.

#### Human-readable context
```
description  str — e.g. "Diesel Fuel — Manchester Depot"
location     str — plant name, site, city, or airport pair
vendor       str — vendor name or code
```

#### Emission calculation
```
emission_factor         FK → EmissionFactor (SET_NULL — snapshot survives EF updates)
emission_factor_value   Decimal(12,6) — snapshot of EF at ingestion time
emission_factor_source  str — e.g. "DEFRA_2023"
total_co2e_kg           Decimal(18,4) = activity_quantity × emission_factor_value
```

**Why snapshot the EF value?** Emission factors are updated annually. If we FK-reference only and the EF changes, historical records would silently recalculate with the new factor, breaking audit reproducibility. Snapshotting the value at ingestion time is the correct approach for audit-grade data.

#### Review workflow
```
status       ENUM(PENDING, FLAGGED, APPROVED, REJECTED, LOCKED)
flag_reason  ENUM(unit_mismatch, outlier_value, missing_ref, duplicate, date_gap, other)
analyst_note text
reviewed_by  FK → User (SET_NULL)
reviewed_at  datetime
```

**Status state machine:**
```
PENDING → APPROVED | REJECTED | FLAGGED
FLAGGED → APPROVED | REJECTED
APPROVED → LOCKED
LOCKED → (terminal — no transitions)
```

`LOCKED` records are rejected by the API at the view layer — no PATCH or action endpoint will modify them. This enforces audit immutability.

#### Audit trail
```
history  HistoricalRecords()  [django-simple-history]
```

Every field change generates a `HistoricalEmissionRecord` row capturing: changed_by user, timestamp, history_type (Create/Update/Delete), and the full field state. This means we can reconstruct the record at any point in time.

---

## Database Indexes

```python
models.Index(fields=['organization', 'status'])   — review queue filtering
models.Index(fields=['organization', 'scope'])    — scope aggregation
models.Index(fields=['organization', 'activity_date']) — date range filtering
models.Index(fields=['batch'])                    — batch detail joins
```

---

## What Would Change at Scale

| Current (prototype) | Production |
|---|---|
| Shared schema, FK filtering | Separate schemas via `django-tenants` |
| SQLite (local) / Postgres (prod) | Postgres with read replicas |
| Synchronous ingestion in request | Celery task for async processing |
| EF snapshot at ingestion | EF versioned with period validity, recalculate API |
| Single organization in demo | True multi-org with org-level admin |
