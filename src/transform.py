"""Transform raw Comtrade pulls into the model tables.

Reads:  data/processed/trade_long.csv  +  config/hs_lanes.yml
Writes: data/processed/lane_year.csv      per-lane per-year both mirror sides
        data/processed/pom_pool.csv       placed-on-market pool (GWh, by segment)
        data/processed/mirror_ratios.csv  AU-CIF / CN-FOB value ratio by lane
        data/processed/flags.csv          tripwires: ratio breaks, >50% moves,
                                          mining-truck arrivals, co-import signature
        data/processed/surplus.csv        trade inflow vs bottom-up reference layer
        data/processed/summary.json       headline numbers for README/CI

Method notes (docs/method.md):
  * Tonnage basis is China-reported netWgt (AU preview-tier netWgt is not
    populated); value basis is AU-reported CIF (the landed cost Australia pays).
  * Mirror ratio = AU CIF / CN FOB on primary value. CIF includes freight and
    insurance, so ~1.0-1.2 is normal; sustained >1.3 or a >50% y/y swing is a
    declaration-gap flag.
  * GWh conversions come exclusively from config/hs_lanes.yml.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROC, DATA_REF, load_config

RATIO_BREAK = 0.50      # y/y swing in mirror ratio that raises a flag
RATIO_BAND = (0.80, 2.00)
MOVE_BREAK = 0.50       # y/y move in value or tonnage that raises a flag
MAT_VALUE = 5e6         # flags only fire above US$5M ...
MAT_TONNES = 200        # ... or 200 t — keeps micro-lanes out of the register
TRIP_VALUE = 2e7        # 870410 tripwire: >US$20M AU CIF in a year ...
TRIP_UNITS = 150        # ... or >150 units = material mining-fleet arrival


def gwh_for(lane: dict, qty: float, netwgt_kg: float) -> float:
    conv = lane.get("conversion") or {}
    method = conv.get("method", "none")
    if method == "kg_per_kwh":
        return (netwgt_kg or 0.0) / conv["kg_per_kwh"] / 1e6
    if method == "kwh_per_unit":
        return (qty or 0.0) * conv["kwh_per_unit"] * conv.get("li_share", 1.0) / 1e6
    return 0.0


def main() -> None:
    cfg = load_config()
    lanes = {str(l["hs"]): l for l in cfg["lanes"]}
    df = pd.read_csv(DATA_PROC / "trade_long.csv", dtype={"cmdCode": str})
    df["cmdCode"] = df["cmdCode"].str.strip()

    cn = df[df.direction == "cn_export"].set_index(["period", "cmdCode"])
    au = df[df.direction == "au_import"].set_index(["period", "cmdCode"])
    years = sorted(df.period.unique())

    rows = []
    for year in years:
        for code, lane in lanes.items():
            c = cn.loc[(year, code)] if (year, code) in cn.index else None
            a = au.loc[(year, code)] if (year, code) in au.index else None
            cn_val = float(c.primaryValue) if c is not None else 0.0
            au_val = float(a.primaryValue) if a is not None else 0.0
            cn_wgt = float(c.netWgt) if c is not None and pd.notna(c.netWgt) else 0.0
            qty = float(c.qty) if c is not None and pd.notna(c.qty) else (
                float(a.qty) if a is not None and pd.notna(a.qty) else 0.0)
            rows.append({
                "year": year, "hs": code, "desc": lane["desc"],
                "segment": lane["segment"], "role": lane["role"],
                "cn_fob_usd": cn_val, "au_cif_usd": au_val,
                "cn_netwgt_t": cn_wgt / 1000.0, "units": qty,
                "mirror_ratio": (au_val / cn_val) if cn_val > 0 else None,
                "gwh": gwh_for(lane, qty, cn_wgt),
            })
    ly = pd.DataFrame(rows)
    for col, nd in (("cn_fob_usd", 2), ("au_cif_usd", 2), ("cn_netwgt_t", 3),
                    ("units", 0), ("mirror_ratio", 4), ("gwh", 6)):
        ly[col] = ly[col].round(nd)
    ly.to_csv(DATA_PROC / "lane_year.csv", index=False)

    # ---- POM pool (battery-energy lanes only) ------------------------------
    pool = ly[ly.role == "pool"].copy()
    pool["cum_gwh"] = pool.groupby("hs")["gwh"].cumsum()
    pool_year = pool.groupby("year", as_index=False)["gwh"].sum()
    pool_year["cum_gwh"] = pool_year.gwh.cumsum()
    pool_year[["gwh", "cum_gwh"]] = pool_year[["gwh", "cum_gwh"]].round(4)
    pool_year.to_csv(DATA_PROC / "pom_pool.csv", index=False)

    # ---- Mirror ratios (lanes with both sides reported) ---------------------
    mr = ly[ly.mirror_ratio.notna()][["year", "hs", "segment", "mirror_ratio"]]
    mr.to_csv(DATA_PROC / "mirror_ratios.csv", index=False)

    # ---- Flags --------------------------------------------------------------
    flags = []
    ly_s = ly.sort_values(["hs", "year"])
    for code, g in ly_s.groupby("hs"):
        lane = lanes[code]
        g = g.set_index("year")
        for year in years:
            if year not in g.index:
                continue
            r = g.loc[year]
            prev = g.loc[year - 1] if (year - 1) in g.index else None
            # mining-truck tripwire: material arrival only
            if lane["role"] == "tripwire" and \
                    (r.au_cif_usd > TRIP_VALUE or r.units > TRIP_UNITS):
                flags.append({"year": year, "hs": code, "kind": "mining-truck arrival",
                              "detail": f"870410 AU CIF US${r.au_cif_usd/1e6:.1f}M "
                                        f"({r.units:.0f} units) — review propulsion split"})
            # mirror-ratio break (material lanes only)
            ratio_ok = r.mirror_ratio is not None and pd.notna(r.mirror_ratio)
            if ratio_ok and r.au_cif_usd >= MAT_VALUE and \
                    not (RATIO_BAND[0] <= r.mirror_ratio <= RATIO_BAND[1]):
                flags.append({"year": year, "hs": code, "kind": "mirror-ratio out of band",
                              "detail": f"ratio {r.mirror_ratio:.2f} outside "
                                        f"{RATIO_BAND[0]}-{RATIO_BAND[1]}"})
            if prev is not None:
                prev_ok = prev.mirror_ratio is not None and pd.notna(prev.mirror_ratio)
                if ratio_ok and prev_ok and prev.mirror_ratio > 0 and \
                        r.au_cif_usd >= MAT_VALUE and \
                        abs(r.mirror_ratio / prev.mirror_ratio - 1) > RATIO_BREAK:
                    flags.append({"year": year, "hs": code, "kind": "mirror-ratio break",
                                  "detail": f"{prev.mirror_ratio:.2f} -> {r.mirror_ratio:.2f} y/y"})
                for col, label, mat in (("au_cif_usd", "value", MAT_VALUE),
                                        ("cn_netwgt_t", "tonnage", MAT_TONNES)):
                    pv, rv = getattr(prev, col), getattr(r, col)
                    if pv > 1e-9 and abs(rv / pv - 1) > MOVE_BREAK and rv > mat:
                        flags.append({"year": year, "hs": code,
                                      "kind": f">{int(MOVE_BREAK*100)}% {label} move",
                                      "detail": f"{label} {pv:,.0f} -> {rv:,.0f} "
                                                f"({rv/pv-1:+.0%})"})
    # storage/swap co-import signature: packs + inverters + cabinets co-surging
    sig = ly[ly.hs.isin(["850760", "850440", "853710"])].pivot_table(
        index="year", columns="hs", values="cn_netwgt_t")
    sig_yoy = sig.pct_change()
    for year in sig_yoy.index:
        row = sig_yoy.loc[year]
        if (row > 0.20).all() and row["850760"] > 0.30:
            flags.append({"year": int(year), "hs": "850760+850440+853710",
                          "kind": "co-import signature",
                          "detail": "packs/inverters/cabinets co-surge "
                                    f"(850760 {row['850760']:+.0%}, 850440 {row['850440']:+.0%}, "
                                    f"853710 {row['853710']:+.0%}) — storage/swap indicator"})
    flags_df = pd.DataFrame(flags)
    flags_df["year"] = flags_df["year"].astype(int)
    flags_df.to_csv(DATA_PROC / "flags.csv", index=False)

    # ---- Surplus vs bottom-up reference layer (validation overlay) ----------
    # Multiple reference rows may share (year, segment) — e.g. home storage +
    # utility-scale both sit inside the 850760 lane. They are summed into one
    # registered total; the residual is UNALLOCATED inflow (C&I, channel
    # inventory, portable packs, unregistered product), not an error term.
    surplus_rows = []
    ref_path = DATA_REF / "installations_bottomup.csv"
    if ref_path.exists():
        ref = pd.read_csv(ref_path, dtype={"hs": str})
        for (yr, segname), grp in ref.groupby(["year", "segment"]):
            seg = ly[(ly.year == yr) & (ly.segment == segname)]
            if seg.empty:
                continue
            trade_gwh = float(seg.gwh.sum())
            ref_gwh = 0.0
            for _, r in grp.iterrows():
                if "gwh" in grp.columns and pd.notna(r.get("gwh")):
                    ref_gwh += float(r["gwh"])
                else:
                    ref_gwh += float(r.units) * float(r.kwh_per_unit) / 1e6
            hs_vals = sorted({str(h) for h in grp.hs if pd.notna(h)})
            surplus_rows.append({
                "year": int(yr),
                "hs": "+".join(hs_vals),
                "segment": segname,
                "trade_inflow_gwh": round(trade_gwh, 3),
                "reference_gwh": round(ref_gwh, 3),
                "surplus_gwh": round(trade_gwh - ref_gwh, 3),
                "source": " | ".join(str(s) for s in grp.source),
            })
    pd.DataFrame(surplus_rows).to_csv(DATA_PROC / "surplus.csv", index=False)

    # ---- Summary ------------------------------------------------------------
    a = cfg["anchors"]
    y0, y1 = cfg["periods"]["annual_start"], cfg["periods"]["annual_end"]
    s76 = ly[(ly.hs == "850760")].set_index("year").gwh
    summary = {
        "years": [int(y0), int(y1)],
        "pom_pool_gwh_by_year": {int(k): round(v, 2)
                                 for k, v in pool_year.set_index("year").gwh.items()},
        "pom_pool_cum_gwh": round(float(pool_year.gwh.sum()), 2),
        "lane_850760_gwh_latest": round(float(s76.get(y1, 0.0)), 2),
        "basket_au_cif_usd_latest": float(ly[ly.year == y1].au_cif_usd.sum()),
        "anchors": {
            "pom_pool_cum_gwh_target": a["pom_pool_cum_gwh_2019_2025"],
            "lane_850760_gwh_target": a["lane_850760_gwh_2025"],
            "tolerance": a["tolerance"],
        },
        "n_flags": len(flags),
        "flags": json.loads(flags_df.to_json(orient="records", force_ascii=False)),
    }
    (DATA_PROC / "summary.json").write_text(
        json.dumps(summary, indent=1, default=lambda o: float(o)), encoding="utf-8")

    print(f"lane_year: {len(ly)} rows | pool cum {summary['pom_pool_cum_gwh']} GWh | "
          f"850760 {y1}: {summary['lane_850760_gwh_latest']} GWh | flags: {len(flags)}")


if __name__ == "__main__":
    main()
