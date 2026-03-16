#!/usr/bin/env python3
"""
Ingest HM Land Registry Price Paid CSV into SQLite.

Creates:
  - property_records    raw data table
  - property_analytics  canonical cleaned view
  - property_fts        full-text search (FTS5)
  - copilot_sessions    chat session storage
  - copilot_feedback    answer quality feedback

Usage:
    python3 src/ingest.py --csv data/pp-2024.csv --db data/uk_property.db
    python3 src/ingest.py --csv data/pp-complete.csv --db data/uk_property.db --append
"""

import argparse
import csv
import sqlite3
import sys
import os
from tqdm import tqdm

# HM Land Registry Price Paid Data columns (no header in file)
HMLR_COLUMNS = [
    "transaction_id",
    "price",
    "date_of_transfer",
    "postcode",
    "property_type",
    "old_new",
    "duration",
    "paon",
    "saon",
    "street",
    "locality",
    "town",
    "district",
    "county",
    "ppd_category_type",
    "record_status",
]

CREATE_RAW = """
CREATE TABLE IF NOT EXISTS property_records (
    transaction_id    TEXT PRIMARY KEY,
    price             INTEGER,
    date_of_transfer  TEXT,
    postcode          TEXT,
    property_type     TEXT,
    old_new           TEXT,
    duration          TEXT,
    paon              TEXT,
    saon              TEXT,
    street            TEXT,
    locality          TEXT,
    town              TEXT,
    district          TEXT,
    county            TEXT,
    ppd_category_type TEXT,
    record_status     TEXT
);
"""

CREATE_VIEW = """
CREATE VIEW IF NOT EXISTS property_analytics AS
SELECT
    transaction_id,
    price                                                                AS price_num,
    date_of_transfer                                                     AS sale_date,
    substr(date_of_transfer, 1, 7)                                       AS sale_month,
    substr(date_of_transfer, 1, 4)                                       AS sale_year,
    postcode,
    CASE
        WHEN length(postcode) >= 5 THEN trim(substr(postcode, 1, instr(postcode, ' ') - 1))
        ELSE postcode
    END                                                                  AS postcode_area,
    CASE property_type
        WHEN 'D' THEN 'Detached'
        WHEN 'S' THEN 'Semi-Detached'
        WHEN 'T' THEN 'Terraced'
        WHEN 'F' THEN 'Flat/Maisonette'
        ELSE 'Other'
    END                                                                  AS property_type_clean,
    CASE old_new
        WHEN 'Y' THEN 1
        ELSE 0
    END                                                                  AS is_new_build,
    CASE duration
        WHEN 'F' THEN 'Freehold'
        WHEN 'L' THEN 'Leasehold'
        ELSE 'Unknown'
    END                                                                  AS tenure_clean,
    paon,
    saon,
    street,
    locality,
    upper(trim(town))                                                    AS town_clean,
    upper(trim(district))                                                AS district_clean,
    upper(trim(county))                                                  AS county_clean,
    ppd_category_type,
    record_status
FROM property_records
WHERE record_status != 'D';
"""

CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS property_fts USING fts5(
    transaction_id UNINDEXED,
    postcode,
    paon,
    saon,
    street,
    locality,
    town,
    district,
    county,
    content='property_records',
    content_rowid='rowid'
);
"""

CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS copilot_sessions (
    session_id   TEXT PRIMARY KEY,
    username     TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now')),
    messages     TEXT DEFAULT '[]'
);
"""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    username     TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""

CREATE_FEEDBACK = """
CREATE TABLE IF NOT EXISTS copilot_feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    username     TEXT,
    question     TEXT,
    answer       TEXT,
    rating       TEXT CHECK(rating IN ('helpful','needs_fix')),
    correction   TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);
"""

EPC_COLUMNS_KEEP = [
    "LMK_KEY", "ADDRESS1", "ADDRESS2", "POSTCODE", "LOCAL_AUTHORITY_LABEL",
    "PROPERTY_TYPE", "BUILT_FORM", "CONSTRUCTION_AGE_BAND",
    "TOTAL_FLOOR_AREA", "NUMBER_HABITABLE_ROOMS", "TENURE",
    "CURRENT_ENERGY_RATING", "LODGEMENT_DATETIME"
]

CREATE_EPC = """
CREATE TABLE IF NOT EXISTS epc_records (
    lmk_key               TEXT PRIMARY KEY,
    address1              TEXT,
    address2              TEXT,
    postcode              TEXT,
    local_authority       TEXT,
    property_type         TEXT,
    built_form            TEXT,
    construction_age_band TEXT,
    total_floor_area      REAL,
    habitable_rooms       INTEGER,
    tenure                TEXT,
    energy_rating         TEXT,
    lodgement_date        TEXT
);
"""

def count_lines(path: str) -> int:
    count = 0
    with open(path, "rb") as f:
        for _ in f:
            count += 1
    return count


def ingest(csv_path: str, db_path: str, append: bool = False):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Schema
    cur.executescript(CREATE_RAW)
    con.commit()

    if not append:
        existing = cur.execute("SELECT COUNT(*) FROM property_records").fetchone()[0]
        if existing > 0:
            confirm = input(
                f"WARNING: This will clear {existing:,} existing records. "
                f"Type 'yes' to continue or use --append to add to existing data: "
            ).strip().lower()
            if confirm != "yes":
                print("Aborted.")
                con.close()
                sys.exit(0)
        print("Clearing existing property_records …")
        cur.execute("DELETE FROM property_records")
        con.commit()

    print(f"Counting rows in {csv_path} …")
    total = count_lines(csv_path)
    print(f"  {total:,} rows found")

    inserted = skipped = 0
    BATCH = 5000

    with open(csv_path, encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        batch = []
        for row in tqdm(reader, total=total, unit="rows", desc="Ingesting"):
            if len(row) < 16:
                skipped += 1
                continue
            rec = dict(zip(HMLR_COLUMNS, row[:16]))
            try:
                rec["price"] = int(rec["price"])
            except (ValueError, TypeError):
                skipped += 1
                continue

            batch.append(tuple(rec[c] for c in HMLR_COLUMNS))
            if len(batch) >= BATCH:
                cur.executemany(
                    f"INSERT OR REPLACE INTO property_records VALUES ({','.join(['?']*16)})",
                    batch,
                )
                inserted += len(batch)
                batch = []

        if batch:
            cur.executemany(
                f"INSERT OR REPLACE INTO property_records VALUES ({','.join(['?']*16)})",
                batch,
            )
            inserted += len(batch)

    con.commit()
    print(f"  Inserted: {inserted:,}  Skipped: {skipped:,}")

    print("Building analytics view …")
    cur.execute("DROP VIEW IF EXISTS property_analytics")
    cur.executescript(CREATE_VIEW)

    print("Building FTS index …")
    fts_exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='property_fts'"
    ).fetchone()
    if fts_exists and append:
        # Incremental update — much faster than full rebuild
        cur.execute("INSERT INTO property_fts(property_fts) VALUES('rebuild')")
    else:
        # Full rebuild
        cur.execute("DROP TABLE IF EXISTS property_fts")
        cur.executescript(CREATE_FTS)
        cur.execute("INSERT INTO property_fts(property_fts) VALUES('rebuild')")

    print("Creating app tables …")
    cur.executescript(CREATE_SESSIONS)
    cur.executescript(CREATE_USERS)
    cur.executescript(CREATE_FEEDBACK)

    con.commit()
    con.close()
    print(f"\nDone. Database: {db_path}")


def main():
    parser = argparse.ArgumentParser(description="Ingest HMLR Price Paid CSV into SQLite")
    parser.add_argument("--csv", required=True, help="Path to HMLR CSV file")
    parser.add_argument("--db", default="data/uk_property.db", help="SQLite DB path")
    parser.add_argument("--append", action="store_true",
                        help="Append to existing data (INSERT OR REPLACE)")
    args = parser.parse_args()
    ingest(args.csv, args.db, args.append)


if __name__ == "__main__":
    main()
