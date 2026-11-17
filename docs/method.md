# Methodology — battery-trade-au

Version 1.0 · applies to pipeline state of the initial commit.
The machine-readable source of truth for lanes and conversions is
`config/hs_lanes.yml`; this document explains and bounds the choices.

---

## 1. Purpose and scope

Quantify the flow of battery energy from China into Australia — by lane,
tonnage, value and implied GWh — from public customs data only, in a form a
stranger can reproduce end-to-end from a fresh clone. The output is the
evidence base for the Australian battery circularity "blind spot": the
placed-on-market (POM) pool implied by trade is far larger than any domestic
registry captures, and it is compounding.

Scope: 41 HS codes (config §lanes), annual frequency 2019–latest, both mirror
directions. Quarterly pulls are supported by the fetcher and enabled in CI when
an API key is present.

## 2. Source register

| # | Source | Role | Access |
|---|--------|------|--------|
| S1 | UN Comtrade API (`comtradeapi.un.org`), annual HS | Primary — all trade records | Free key (env `COMTRADE_API_KEY`) or public preview tier |
| S2 | ITC Trade Map | Fallback / cross-check for Comtrade gaps | Manual, documented in issue if used |
| S3 | ABS / DFAT statistical releases | Australian-side corroboration | Manual |
| S4 | EV Council, *State of EVs* | Reference overlay: BEV/PHEV sales | `data/reference/installations_bottomup.csv` |
| S5 | Clean Energy Regulator, CHBP registrations | Reference overlay: home-battery installs | same |
| S6 | Recorded calibration anchors (2026-11 verified analysis cycle) | Validation-gate targets only | `config/hs_lanes.yml → anchors` |

Reference-layer files are validation overlays and are **never** mixed into the
trade series; they appear only in `surplus.csv` and its chart.

## 3. Conventions

### 3.1 Mirror construction
Every period pulls reporter 156→partner 36 flow X (China-export side) and
reporter 36→partner 156 flow M (Australia-import side). No record is
interpolated; missing lane-year cells are zero-flow or unreported, and the two
are distinguished by the raw payloads in `data/raw/`.

### 3.2 Tonnage and value bases
- **Tonnage:** China-reported `netWgt`. The Australian preview-tier records do
  not carry usable net weight for these lanes (`isNetWgtEstimated`, zero-filled),
  while China's are reported values. All kg→kWh conversions therefore run off
  the China side.
- **Value:** Australia-reported CIF (`primaryValue`) for landed cost; China FOB
  for the mirror denominator.
- **850760 mixture:** the lane carries 12–21 M items/yr (cells through packs).
  Small-format mass at consumer-cell weights aggregates to <1 kt against
  ~250 kt total tonnage, so tonnage is treated as large-format for pool purposes.
  This is a stated approximation, bounded by the validation gate (§6).

### 3.3 Energy conversion
Two methods, both config-driven:
`kg_per_kwh` (tonnage ÷ pack-level kg/kWh — used for 850760 at 8.0 kg/kWh,
≈125 Wh/kg blended pack density) and `kwh_per_unit × li_share` (vehicle and
industrial lanes — pack sizes from OEM specs, Li-share for forklift/works-truck
lanes where lead-acid persists). Every GWh figure in the outputs divides a
Comtrade record by exactly one published config row.

### 3.4 Mirror ratio
`mirror_ratio = AU CIF / CN FOB` on primary value. Normal CIF/FOB lift is
~1.05–1.20. Sustained >1.3 (lead-acid: 1.5–1.9×) indicates declaration gaps;
<0.8 indicates re-export/transhipment noise or misdeclaration.

## 4. Tripwires (flags.csv)

| Flag | Trigger |
|------|---------|
| mining-truck arrival | 870410 AU CIF > US$20M or >150 units in a year (code unsplit by propulsion — always manual review) |
| mirror-ratio break | y/y ratio swing > 50% on a lane ≥ US$5M |
| mirror-ratio out of band | ratio outside 0.80–2.00 on a lane ≥ US$5M |
| >50% value / tonnage move | y/y move > 50% above US$5M / 200 t materiality |
| co-import signature | 850760, 850440 and 853710 all grow > 20% y/y with 850760 > 30% — the storage/swap assembly pattern |

`flags.csv` is the full-series register; the quarterly workflow surfaces only
latest-period flags in its summary issue.

## 5. Reference overlay and the unregistered surplus

`surplus.csv` compares trade-derived inflow against bottom-up registered
installations where a public anchor exists (EVC sales for passenger EV/PHEV;
CER CHBP registrations for home storage). Differences are *not* errors: imports
lead installations (stock, registration lag), reference sales include non-China
origin, and CHBP coverage is partial-year. The comparison exists to size the
pool that no registry sees, with each row carrying its source.

## 6. Validation gate

`src/validate.py` fails the run (exit 1, nothing committed in CI) unless:

| Check | Target | Tolerance |
|-------|--------|-----------|
| POM pool, cumulative 2019–2025 | 70.9 GWh | ±10% |
| 850760 GWh, latest year | 31.0 GWh | ±10% |

Anchors are calibration targets recorded from the verified 2026-11 analysis
cycle. They are compared against, never read into, the model. If Comtrade
revises history and the gate trips, that is the gate working: inspect the
revision before touching a conversion factor.

## 7. Known limitations

1. **850760 format mix** — see §3.2; bounded by the gate, and by the AU-side
   unit-value cross-check possible in future iterations.
2. **870410 is unsplit by propulsion** — it is a watch item, never a pool lane.
3. **CIF ≠ FOB** — mirror ratios embed freight/insurance; they are diagnostics,
   not discrepancy proof.
4. **Preview-tier AU netWgt** — absent; if a future API tier exposes Australian
   net weight, the model gains a second tonnage basis without structural change.
5. **HS2022 vintages** — early years are harmonised to HS2022 codes by Comtrade;
   pre-2022 cells may carry estimation flags preserved in `data/raw/`.
6. **HEV/PHEV split in 870451** — hybrid utes carry 1.5–2 kWh (HEV) to ~30 kWh
   (PHEV); the config uses the HEV value and flags the split as the open
   variable pending a make/model layer.

## 8. Update operations

Quarterly (15 Jan / Apr / Jul / Oct, Sydney morning) and on manual dispatch:
fetch → transform → validate-gate → commit CSVs + charts → summary issue with
latest-period flags. Manual refresh: `python src/fetch.py --start 2025 --end 2026`
then transform/validate/charts as in the README.
