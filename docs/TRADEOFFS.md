# TRADEOFFS.md — Three Things Deliberately Not Built

## 1. Real-time SAP OData / BAPI / RFC Integration

**What it would look like:** Instead of file upload, the system would poll SAP via OData (`/sap/opu/odata/sap/MM_PUR_PO_MAINT_V2_SRV/`) or BAPI (`BAPI_PO_GETDETAIL`) on a schedule, pulling new procurement documents automatically.

**Why I didn't build it:**
- Requires SAP Basis-level connectivity: RFC destination configuration, service user with S_RFC auth, firewall rules, VPN or BTP connectivity
- OData endpoint shape varies significantly by SAP version (ECC vs S/4HANA) and client customization
- For a 4-day prototype, this connectivity cannot be established even with mock data — the parsing logic (plant codes, material classification, unit normalization) is where the real intellectual work is, and that's fully implemented
- The file upload interface is how this actually works at most clients for the first 6–12 months anyway, while SAP integration is negotiated with their Basis team

**What would be needed in production:** SAP BTP connectivity service or a Boomi/MuleSoft integration layer; RFC destination configs; a Celery task polling on a configurable schedule; error handling for SAP downtime windows.

---

## 2. PDF Utility Bill Parsing (OCR)

**What it would look like:** Accept PDF utility bills directly, extract meter readings, billing periods, and kWh values using OCR (Tesseract or a commercial API like AWS Textract or Google Document AI).

**Why I didn't build it:**
- OCR on utility bills has ~85–90% field-level accuracy in good conditions, dropping to 60% on scanned/faxed bills with unusual formatting
- For audit-grade carbon data, a 10–15% error rate on consumption values is unacceptable without very robust correction workflows
- The variance in PDF layout across UK utilities (EDF, British Gas, E.ON, Scottish Power, npower) means each provider would need a custom extraction template
- CSV export achieves the same goal with 100% field accuracy and is available from all major UK utility portals
- OCR is the right answer for SME clients who don't have portal access; it's a separate feature that deserves a dedicated sprint with proper evaluation of commercial extraction APIs

**What would be needed:** LLM-based document extraction (e.g., Gemini Pro Vision with a structured extraction prompt) is actually promising here — better than traditional OCR — but still requires significant QA and analyst correction workflows. Add as TRADEOFF to present to the PM.

---

## 3. Multi-Currency FX Normalization for Spend-Based Scope 3

**What it would look like:** For Scope 3 categories where activity data isn't available (e.g., insurance, professional services, cloud computing — Category 1 purchased goods/services), companies use spend-based emission factors (kgCO2e per £/$ of spend). This requires normalizing all transaction currencies to a common reporting currency using date-accurate FX rates.

**Why I didn't build it:**
- The spend-based method is lowest-quality (Tier 3) per GHG Protocol — used only when activity data is unavailable
- All three source types in this prototype support activity-based calculation (liters, kWh, km, nights) — the superior Tier 1/2 approach
- FX rate data requires a daily rates feed (ECB, Fixer.io, or similar) and a separate model to store historical rates
- Implementing spend-based EFs without FX normalization produces incorrect results — better to be explicit that it's not implemented than to produce wrong numbers
- The analyst review UI would need a separate "spend-based records" section with different validation rules

**What I'd tell the PM:** "We can add spend-based Scope 3 calculation for categories like professional services and IT in the next sprint. We'll need a daily FX rate feed integrated and a conversation about which EEIO (Environmentally Extended Input-Output) factor database to use — EXIOBASE, USEEIO, or a commercial provider like Watershed's factor library."
