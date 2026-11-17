"""Validation gate — fails loudly if reproduced totals leave the anchor envelope.

Anchors (config/hs_lanes.yml -> anchors) are calibration targets recorded from
the verified 2026-11 analysis cycle:
  * cumulative placed-on-market pool 2019-2025 = 70.9 GWh
  * 850760 (large-format packs) 2025           = ~31 GWh
Exit code 1 = build broken; CI must not commit refreshed data on a failed gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROC


def check(name: str, actual: float, target: float, tol: float) -> bool:
    lo, hi = target * (1 - tol), target * (1 + tol)
    ok = lo <= actual <= hi
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {actual:.2f} vs target {target:.2f} "
          f"(envelope {lo:.2f}-{hi:.2f})")
    return ok


def main() -> int:
    summary = json.loads((DATA_PROC / "summary.json").read_text(encoding="utf-8"))
    a = summary["anchors"]
    tol = float(a["tolerance"])
    print("Validation gate — anchor reproduction")
    ok = True
    ok &= check("POM pool cumulative GWh",
                summary["pom_pool_cum_gwh"], a["pom_pool_cum_gwh_target"], tol)
    ok &= check("850760 GWh (latest year)",
                summary["lane_850760_gwh_latest"], a["lane_850760_gwh_target"], tol)
    if not ok:
        print("\nGATE FAILED — outputs not committed. Inspect config/hs_lanes.yml "
              "conversions or the upstream Comtrade revision before merging.")
        return 1
    print("\nGate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
