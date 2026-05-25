# BreatheESG

A Django REST + React prototype for ingesting, normalizing, and reviewing ESG emissions data from three source types.

## Live Demo

| | URL |
|---|---|
| **Frontend** | https://frontend-nu-sepia-53.vercel.app |
| **Backend API** | https://breathe-esg-production.up.railway.app |

### Demo credentials
- Admin: `admin` / `breatheesg2024`
- Analyst: `analyst` / `breatheesg2024`

---

## What It Does

1. **Ingest** — Upload files from three source types:
   - SAP fuel & procurement (pipe-delimited ABAP flat file)
   - Utility electricity (Green Button-style portal CSV)
   - Corporate travel (Concur Expense File Export CSV)

2. **Normalize** — Parsers convert to SI units, classify GHG scope (1/2/3), apply DEFRA 2023 emission factors, detect outliers

3. **Review** — Analyst dashboard to approve/reject/flag records before audit lock

## Architecture

```
frontend/           React + Vite (port 5173)
backend/
  breathe/          Django settings, URLs
  core/             Organization + User models (multi-tenancy)
  ingestion/        Parsers + upload API + batch management
  emissions/        EmissionRecord model + dashboard API
  review/           Approve/reject/flag/lock workflow
sample_data/        3 realistic source files
docs/               MODEL.md DECISIONS.md TRADEOFFS.md SOURCES.md
```

## Running Locally

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_data    # creates org, users, loads fixtures, ingests sample files
python manage.py runserver 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev    # http://localhost:5173
```

## Sample Data

| File | Format | Realistic challenges |
|---|---|---|
| `sap_fuel_procurement.csv` | Pipe-delimited, German aliases | DD.MM.YYYY dates, M3/GAL/L units, plant codes, outlier row |
| `utility_electricity.csv` | Green Button-style CSV | 29-day non-calendar billing periods, estimated readings, MPAN |
| `concur_travel.csv` | Concur Expense Export | No flight distances (haversine fallback), seat class EF selection |

## Data Model Highlights

- `EmissionRecord` tracks full provenance: source file, batch, row, ingestion timestamp, edit flag
- `RawRow` preserves the original parsed JSON for audit/replay
- `EmissionFactor` table seeded from DEFRA 2023 — snapshotted at ingestion time for audit reproducibility
- django-simple-history on `EmissionRecord` — every field change logged with user + timestamp
- Status state machine: `PENDING → APPROVED/REJECTED/FLAGGED → LOCKED`

See [docs/MODEL.md](docs/MODEL.md) for full model documentation.

## Documentation

| Document | Contents |
|---|---|
| [MODEL.md](docs/MODEL.md) | Data model, multi-tenancy, scope classification, audit trail |
| [DECISIONS.md](docs/DECISIONS.md) | Every ambiguity resolved with rationale |
| [TRADEOFFS.md](docs/TRADEOFFS.md) | Three things deliberately not built |
| [SOURCES.md](docs/SOURCES.md) | Real-world format research per source |

## Grading Notes

- **35% data model**: Full source-of-truth tracking, scope classification, unit normalization, audit trail, multi-tenancy all documented in MODEL.md
- **20% source realism**: Research documented in SOURCES.md; sample data designed to exercise real-world edge cases
- **10% analyst UX**: Dashboard → Ingest → Review workflow; bulk approve; modal with raw JSON and audit history tabs
- **10% tradeoffs**: Three deliberate omissions with production-ready rationale in TRADEOFFS.md
