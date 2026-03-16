# UK Property Market Copilot

Smart analytics copilot for the UK residential property market, powered by HM Land Registry open data.

## Data Source

All data is sourced from **HM Land Registry Price Paid Data** (GOV.UK), which tracks every residential property sale in England and Wales registered since January 1995. The dataset is published under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

> Contains HM Land Registry data © Crown copyright and database right 2025. This data is licensed under the Open Government Licence v3.0.

## Features

* **Automated data ingestion** from HM Land Registry monthly CSV files (no manual Excel import needed).
* **Full UK property transaction history** from 1995 – 30M+ records.
* **SQLite** local storage with FTS5 full-text search across address fields.
* **AI copilot** for intelligent Q&A: average prices by town/county, new-build vs resale, leasehold vs freehold trends, monthly volume analysis, etc.
* **Canonical analytics view** with cleaned fields:
  - `town_clean`, `county_clean`, `postcode_area`
  - `property_type_clean` (Detached / Semi-Detached / Terraced / Flat / Other)
  - `tenure_clean` (Freehold / Leasehold)
  - `is_new_build`
  - `price_num`, `sale_date`
* **Browser UI** with:
  - Multi-user chat sessions
  - Secure login / register (username + password)
  - Optional Google SSO (`GOOGLE_CLIENT_ID` required)
  - Global filters: county, property type, tenure, date range
  - Records explorer with postcode/town search
  - Dashboards: KPIs, top towns by volume & price, monthly trend, new-build vs resale split, leasehold vs freehold mix
  - Answer feedback buttons (`Helpful` / `Needs Fix`)
* **CENTRAL7 branding** (`#e72026`, `#fcfeff`)

## Requirements

- Python 3.11+
- pip

## Quick Start

### 1. Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

### 2. Configure API key

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 3. Download & ingest HM Land Registry data

Download a year file (e.g. 2024) and import it:

```bash
# Download directly from HM Land Registry (example: 2024 full year)
python3 scripts/download_hmlr_data.py --year 2024 --output data/

# Import into SQLite
python3 src/ingest.py --csv data/pp-2024.csv --db data/uk_property.db
```

Or ingest the complete dataset (all years, ~3 GB):

```bash
python3 scripts/download_hmlr_data.py --complete --output data/
python3 src/ingest.py --csv data/pp-complete.csv --db data/uk_property.db
```

### 4. Run the browser UI

```bash
python3 -m uvicorn src.webapp:app --host 0.0.0.0 --port 8000 --reload
```

Open: `http://localhost:8000`

## HM Land Registry Data Fields

| Field | Description |
|---|---|
| Transaction ID | Unique identifier |
| Price | Sale price (GBP) |
| Date of Transfer | Sale date |
| Postcode | UK postcode |
| Property Type | D=Detached, S=Semi-Detached, T=Terraced, F=Flat/Maisonette, O=Other |
| Old/New | Y=New build, N=Established residential |
| Duration | F=Freehold, L=Leasehold, U=Unknown |
| PAON | Primary Addressable Object Name (house number/name) |
| SAON | Secondary Addressable Object Name (flat/unit) |
| Street | Street name |
| Locality | Locality |
| Town/City | Town or city |
| District | Local authority district |
| County | County |
| PPD Category Type | A=Standard, B=Additional (e.g. repossessions) |
| Record Status | A=Addition, C=Change, D=Delete |

## Auth Configuration

* Local auth works out of the box (register / login).
* For Google SSO, set in `.env`:

```
GOOGLE_CLIENT_ID=your_google_web_client_id
AUTH_SECRET=replace_with_a_strong_secret
```

## Deploy to Railway

1. Push this repo to GitHub.
2. In Railway: `New Project` → `Deploy from GitHub Repo` → select this repo.
3. Add environment variables:
   * `OPENAI_API_KEY`
   * `OPENAI_MODEL` (optional, default `gpt-4o`)
   * `AUTH_SECRET` (required in production)
   * `GOOGLE_CLIENT_ID` (optional)
4. Add a persistent volume mounted at `/app/data` (to persist `data/uk_property.db`).
5. Deploy — Railway will use the `Dockerfile`.
6. Open the Railway domain and test login + chat + dashboard.

## Accuracy Loop

* Copilot answers append an **Evidence** section with executed SQL queries and row counts.
* Down-vote incorrect answers and provide expected answer text.
* Feedback stored in `copilot_feedback` table for prompt iteration.
* Property search behaviour is deterministic:
  - England & Wales data only (HM Land Registry scope)
  - Price ranges validated against realistic UK market bounds
  - County/town disambiguation handled automatically
  - New-build premium highlighted in responses

## CLI Copilot (optional)

```bash
python3 src/copilot.py --db data/uk_property.db
```

## Brand Asset

* Current UI uses: `web/assets/central7-logo.svg`
* Replace with official PNG/SVG anytime, keeping the same filename/path.

## Licence

Data: Open Government Licence v3.0 — HM Land Registry  
Code: MIT
