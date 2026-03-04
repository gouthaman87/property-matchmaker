"""
Download EPC (Energy Performance Certificate) data.
Requires free registration at https://epc.opendatacommunities.org

Usage:
    python3 scripts/download_epc_data.py --token YOUR_API_TOKEN --region london --output data/
"""
import argparse, os, requests

BASE = "https://epc.opendatacommunities.org/api/v1/domestic/search"

def download(token, region, output):
    headers = {"Authorization": f"Basic {token}", "Accept": "text/csv"}
    params = {"size": 5000, "from": 0}
    if region:
        params["local-authority"] = region
    os.makedirs(output, exist_ok=True)
    dest = os.path.join(output, f"epc_{region or 'all'}.csv")
    with open(dest, "w") as f:
        while True:
            r = requests.get(BASE, headers=headers, params=params)
            r.raise_for_status()
            chunk = r.text
            f.write(chunk)
            if len(chunk.strip().splitlines()) < 5001:
                break
            params["from"] += 5000
    print(f"Saved: {dest}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--token", required=True)
    p.add_argument("--region", default="")
    p.add_argument("--output", default="data/")
    args = p.parse_args()
    download(args.token, args.region, args.output)