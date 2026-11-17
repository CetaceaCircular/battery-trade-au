"""Fetch China<->Australia trade data from UN Comtrade for every lane in config.

Two mirror directions per period:
  - China-reported exports to Australia (reporter 156, partner 36, flow X)
  - Australia-reported imports from China (reporter 36, partner 156, flow M)

Auth: set COMTRADE_API_KEY (GitHub Secret / env) for the subscription tier
(multi-period calls, high rate limits). Without a key the script falls back to
the public preview tier (one period per call, ~100 calls/hour, 1 req/sec) —
fully functional for the annual run, just slower.

Outputs:
  data/raw/comtrade_{cn_export|au_import}_{year}.json   (raw API payloads)
  data/processed/trade_long.csv                         (tidy long table)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROC, DATA_RAW, lane_codes, load_config

BASE_SUB = "https://comtradeapi.un.org/data/v1/get"
BASE_PUB = "https://comtradeapi.un.org/public/v1/preview"

FIELDS = [
    "period", "direction", "reporterCode", "partnerCode", "flowCode",
    "cmdCode", "qtyUnitCode", "qty", "netWgt", "isNetWgtEstimated",
    "grossWgt", "primaryValue", "cifvalue", "fobvalue",
]

DIRECTIONS = {
    "cn_export": {"reporterCode": 156, "partnerCode": 36, "flowCode": "X"},
    "au_import": {"reporterCode": 36, "partnerCode": 156, "flowCode": "M"},
}


def have_key() -> str | None:
    key = os.environ.get("COMTRADE_API_KEY", "").strip()
    return key or None


def call_api(year: int, direction: dict, codes: list[str], key: str | None,
             freq: str = "A") -> list[dict]:
    """One API call for a period+direction covering all lane codes."""
    params = {
        "reporterCode": direction["reporterCode"],
        "partnerCode": direction["partnerCode"],
        "flowCode": direction["flowCode"],
        "cmdCode": ",".join(codes),
        "period": str(year) if freq == "A" else year,  # quarterly passes e.g. 202501
    }
    if key:
        url = f"{BASE_SUB}/C/{freq}/HS"
        headers = {"Ocp-Apim-Subscription-Key": key}
    else:
        url = f"{BASE_PUB}/C/{freq}/HS"
        headers = {}
    for attempt in range(5):
        resp = requests.get(url, params=params, headers=headers, timeout=120)
        if resp.status_code == 429:
            wait = 20 * (attempt + 1)
            print(f"  rate-limited; waiting {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("error"):
            raise RuntimeError(f"Comtrade error: {payload['error']}")
        return payload.get("data", [])
    raise RuntimeError("Comtrade rate limit persisted after retries")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=None)
    ap.add_argument("--end", type=int, default=None)
    args = ap.parse_args()

    cfg = load_config()
    codes = lane_codes(cfg)
    start = args.start or cfg["periods"]["annual_start"]
    end = args.end or cfg["periods"]["annual_end"]
    key = have_key()
    print(f"Comtrade tier: {'subscription (key found)' if key else 'public preview (no key)'}")
    print(f"Lanes: {len(codes)} | Years: {start}-{end}")

    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for year in range(start, end + 1):
        for dname, dconf in DIRECTIONS.items():
            raw_path = DATA_RAW / f"comtrade_{dname}_{year}.json"
            data = call_api(year, dconf, codes, key)
            raw_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
            print(f"  {year} {dname}: {len(data)} records -> {raw_path.name}")
            for rec in data:
                rows.append({
                    "period": year,
                    "direction": dname,
                    **{k: rec.get(k) for k in FIELDS if k not in ("period", "direction")},
                })
            if not key:
                time.sleep(1.2)  # preview tier: ~1 req/sec

    out = DATA_PROC / "trade_long.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["period", "direction"] + FIELDS[2:])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
