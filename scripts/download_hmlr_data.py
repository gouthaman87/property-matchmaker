#!/usr/bin/env python3
"""
Download HM Land Registry Price Paid Data from GOV.UK.

Usage:
    python3 scripts/download_hmlr_data.py --year 2024 --output data/
    python3 scripts/download_hmlr_data.py --complete --output data/
    python3 scripts/download_hmlr_data.py --monthly --year 2025 --month 1 --output data/
"""

import argparse
import os
import sys
import requests
from tqdm import tqdm

BASE_URL = "http://prod1.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com"

COMPLETE_FILE = "pp-complete.csv"
YEAR_FILE_TEMPLATE = "pp-{year}.csv"
MONTHLY_FILE_TEMPLATE = "pp-{year}-{month:02d}.csv"  # some months use this pattern


def download_file(url: str, dest_path: str):
    """Stream-download a file with a progress bar."""
    print(f"Downloading: {url}")
    resp = requests.get(url, stream=True, timeout=120)
    if resp.status_code == 404:
        print(f"  ERROR: File not found at {url}", file=sys.stderr)
        sys.exit(1)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

    with open(dest_path, "wb") as f, tqdm(
        total=total, unit="B", unit_scale=True, desc=os.path.basename(dest_path)
    ) as bar:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            bar.update(len(chunk))

    print(f"  Saved to: {dest_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download HM Land Registry Price Paid Data"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--complete", action="store_true",
                       help="Download the full dataset (all years, ~3 GB)")
    group.add_argument("--year", type=int,
                       help="Download full-year file (e.g. 2024)")
    group.add_argument("--monthly", action="store_true",
                       help="Download a specific month file (requires --year and --month)")

    parser.add_argument("--month", type=int, choices=range(1, 13),
                        help="Month number (1-12), used with --monthly")
    parser.add_argument("--output", default="data/",
                        help="Output directory (default: data/)")
    args = parser.parse_args()

    if args.complete:
        url = f"{BASE_URL}/{COMPLETE_FILE}"
        dest = os.path.join(args.output, COMPLETE_FILE)
        download_file(url, dest)

    elif args.year:
        filename = YEAR_FILE_TEMPLATE.format(year=args.year)
        url = f"{BASE_URL}/{filename}"
        dest = os.path.join(args.output, filename)
        download_file(url, dest)

    elif args.monthly:
        if not args.year or not args.month:
            parser.error("--monthly requires --year and --month")
        filename = MONTHLY_FILE_TEMPLATE.format(year=args.year, month=args.month)
        url = f"{BASE_URL}/{filename}"
        dest = os.path.join(args.output, filename)
        download_file(url, dest)


if __name__ == "__main__":
    main()
