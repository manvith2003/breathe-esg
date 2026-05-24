# SOURCES.md — Research Behind Each Data Source

## Source 1: SAP Fuel & Procurement

### What I researched

SAP's procurement data lives primarily in two table families:
- **EKKO / EKPO** — Purchase Order headers and line items
- **MSEG / MKPF** — Material movement documents (goods receipts, issues)
- **MARA / MARC** — Material master (material descriptions, base units)

SAP can expose this data via:
1. **IDoc (Intermediate Document):** Hierarchical fixed-length text format, segment-based (E1EDK01 = header, E1EDP01 = item). Requires EDI middleware to parse.
2. **OData Service:** RESTful JSON/XML over HTTP (`/sap/opu/odata/`). Requires RFC connectivity.
3. **BAPI:** Remote-callable function modules (e.g. `BAPI_PO_GETDETAIL`). Requires RFC.
4. **ABAP flat file (Z-program):** Custom ABAP program queries tables directly and writes a CSV/pipe file. Most common real-world integration method.

I chose option 4 because it reflects what actually happens: an SAP developer writes a Z-report (custom ABAP) that queries MSEG for fuel movements, joins to EKPO for PO details and MARA for material descriptions, and writes a pipe-delimited file to an application server folder or SFTP.

### What I learned

- SAP uses German column names in many standard exports: `Menge` (quantity), `Einheit` (unit of measure), `Werk` (plant), `Buchungsdatum` (posting date)
- Unit of measure codes are SAP-internal: `L` (liter), `GAL` (US gallon), `M3` (cubic meter), `KG` (kilogram), `KWH` (kilowatt-hour)
- Dates default to `DD.MM.YYYY` in German-locale SAP systems
- Plant codes are meaningless without a lookup table — `P001` could be anything
- Material numbers are client-specific; material descriptions are the only reliable way to classify fuel types

### What my sample data looks like and why

`sap_fuel_procurement.csv` is pipe-delimited with 24 rows across Q1–Q2 2024.

Realistic features included:
- Mix of English and German column names to demonstrate alias handling
- DD.MM.YYYY date format for 90% of rows (the SAP German-locale default)
- Materials: `DIESEL-001`, `PETROL-001`, `NGAZ-001` (Erdgas = natural gas), `LPG-001`
- Units: L (standard), GAL (US gallon — for an imported fleet), M3 (natural gas)
- Plant codes: PLANT_001 through PLANT_005 (resolved via lookup table)
- One row with missing QUANTITY (row 15) — tests error path
- One row with unusually high volume: 18,500 L diesel (row 20) — triggers outlier detection (>3σ)
- One row with missing VENDOR_ID — tests warning path

### What would break in a real deployment

1. **Plant code lookup table** — our table has ~10 plant codes; a real SAP client might have 500+ plants across multiple company codes. Would need to load from SAP's plant master (`T001W` table).
2. **Material classification** — our keyword matching (diesel, petrol, etc.) fails on client-specific material numbers like `Z-FUEL-003`. Need a configurable mapping table or ML classification.
3. **Unit conversions** — gallons in our system assumes US gallons; UK SAP systems sometimes use imperial (UK gallons = 4.546L, not 3.785L).
4. **Multi-company-code** — large enterprise clients have multiple company codes in one SAP system, each with different plant hierarchies and chart of accounts.
5. **ABAP extract variation** — different clients' Z-programs produce different column names. The alias mapping would need to be configurable per client.

---

## Source 2: Utility Electricity

### What I researched

UK utility portals typically offer:
- **CSV export** from the portal's "Reports" or "Data Downloads" section
- **Green Button** format (US standard, adopted by some UK smart meter platforms)
- **PDF statements** (most common for smaller accounts)
- **Half-hourly data** for large industrial consumers via Data Collector / Data Aggregator

The UK electricity metering infrastructure uses:
- **MPAN** (Meter Point Administration Number): 21-digit unique identifier for each supply point
- **HH (Half-Hourly) data**: Required for industrial consumers >100kW, delivered via Data Collectors
- **NHH (Non-Half-Hourly)**: For smaller consumers, meter-read-based billing

Billing periods in the UK:
- Domestic: monthly or quarterly
- Commercial: monthly
- Industrial: monthly or 28/29/30-day cycles that don't align with calendar months
- Read dates are the utility's own — not the 1st of the month

### What I learned

- EDF Energy, British Gas Business, and E.ON Business all offer CSV exports from their online portals with similar but not identical column schemas
- Green Button CSV (used in the US and some UK smart meter platforms) uses `Interval Block` and `Interval Reading` XML, but CSV exports simplify this to `timestamp, kWh, cost`
- The key challenge is **billing period alignment**: a company reports calendar-year emissions but billing periods cross month boundaries. Our model stores exact `reporting_period_start` and `reporting_period_end` to handle this correctly — the analyst can see exactly which months each bill covers
- Estimated readings (utility can't access the meter) are common and should be flagged because they may be corrected in the next bill

### What my sample data looks like and why

`utility_electricity.csv` has 25 rows across 5 sites with 29-day billing cycles.

Realistic features:
- Five sites: London HQ (2 meters), Manchester Depot (2 meters), Birmingham DC, Leeds Warehouse, Glasgow Operations
- 29-day cycles crossing month boundaries (e.g., 2024-01-29 → 2024-02-26)
- MPAN numbers in UK format (21 digits)
- Two estimated readings flagged with `is_estimated=Y`
- Mix of tariffs: BUSINESS_FLAT_DAY, BUSINESS_TOU, SME_STANDARD, COLD_STORAGE_RATE

### What would break in a real deployment

1. **Meter aggregation** — sites often have multiple meters (floor by floor, or landlord vs tenant supply). Our model stores per-meter, but reporting requires site-level aggregation.
2. **Estimation corrections** — utilities issue corrected bills that effectively retroactively change a previous period's consumption. The model would need a correction/amendment mechanism.
3. **Smart meter HH data** — half-hourly readings produce 17,520 rows per meter per year. Our current model handles billing-period-level data; HH integration would require aggregation before storage.
4. **Market-based Scope 2** — if the client has PPAs (Power Purchase Agreements) or REGO certificates, the location-based factor doesn't apply. Market-based requires certificate tracking.
5. **Scottish Power and SSE** export formats differ from EDF/British Gas — column names vary enough to need provider-specific adapters.

---

## Source 3: Corporate Travel (Concur)

### What I researched

SAP Concur is the dominant corporate travel and expense platform for enterprise clients. Data access options:

1. **Expense Reports API v4** (OAuth2 JSON): Requires Concur app registration, OAuth scopes (`expense.report.read`), and tenant admin provisioning
2. **Expense File Export**: CSV bulk export from Reports module, configurable columns, no API key
3. **Concur Intelligence / Analytics**: SQL-based data warehouse queries (enterprise tier)
4. **Navan (formerly TripActions)**: Similar SaaS platform; offers a Reporting API and CSV export

The key carbon calculation challenge: expense data is financial, not physical. You know what was spent, not always how far someone flew or how many nights they stayed.

For flights specifically: if a booking shows route LHR→JFK with a cost, you need the distance. Concur does store the itinerary for booked-through-Concur trips, but for out-of-pocket reimbursements, you only get the receipt amount and airline.

### What I learned

- IATA airport codes are the most reliable route identifier — corporate booking systems almost always have origin/destination codes
- Great-circle distance (haversine) is the standard methodology for flight emissions when actual distance isn't provided. DEFRA explicitly endorses this approach.
- Radiative Forcing (RF) multiplier: high-altitude aviation has additional warming effects beyond CO2 alone. DEFRA 2023 factors already include a 1.9× RF multiplier in the published factors — so we don't need to apply it separately.
- Short-haul/long-haul boundary: DEFRA uses 3,700km. Below that, short-haul factors apply; above, long-haul.
- Business class vs economy: significantly different EF. DEFRA 2023: LH economy = 0.195 kgCO2e/km, LH business = 0.429 kgCO2e/km (≈2.2× higher per seat).
- Hotel emissions: DEFRA provides a single UK average factor (31.0 kgCO2e/night). Country-specific factors are available but add complexity.

### What my sample data looks like and why

`concur_travel.csv` has 35 rows covering Jan–May 2024 for 6 travelers.

Realistic features:
- **Flights with no `distance_km`**: Most rows have only IATA codes (LHR, JFK, SIN, etc.) — triggers haversine calculation
- **Both seat classes**: Economy and business class (RPT-2024-003, RPT-2024-011) — different EF applied
- **Hotels with explicit nights**: Some rows; others require check_in/check_out derivation
- **Ground transport with distance**: Taxi/car rental rows with explicit km; one Uber row without km → analyst flag
- **Multi-currency**: GBP, USD, EUR, AED, INR — not normalized (activity-based EF, currency irrelevant)
- **Long-haul routes**: LHR→SIN (10,841km), LHR→SYD (17,016km), LHR→NBO (6,830km) — all long-haul
- **Row with unrecognized expense type** (row 34: "Rideshare" with no airports or distance) — tests error path

### What would break in a real deployment

1. **Airport code coverage**: Our haversine lookup has 58 airports. The IATA database has 40,000+. Regional airports, charter destinations, and country codes (not IATA) would fail our lookup.
2. **Mixed booking channels**: Employees booking directly with airlines (not through Concur's travel booking module) produce expenses with no itinerary data — only a receipt amount. Would need spend-based fallback.
3. **Train travel**: Concur tracks rail expenses but we classify all ground transport as taxi. Train has significantly lower EF (0.035 kgCO2e/km vs 0.149 for taxi). Need expense type disambiguation.
4. **Hotel country specificity**: DEFRA has UK hotel EF. International hotels have different EFs (e.g., US hotels average ~42 kgCO2e/night). Using UK factor for a Dubai hotel is an overestimate.
5. **Group bookings**: A meeting with 10 employees on the same flight should be 10× the single-trip EF. Concur tracks per-employee, so this should work — but requires careful deduplication if multiple employees submit the same flight.
