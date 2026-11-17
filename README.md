# battery-trade-au

**China → Australia battery trade, measured from both sides of the customs mirror.**

A public, reproducible, self-updating data model of battery-energy flows from
China into Australia — 41 HS lanes, both mirror directions, 2019 → latest —
built as the evidence base for one structural fact: **Australia imports
large-format battery energy at a scale its domestic collection, reuse and
recycling infrastructure was never sized for.** Trade classifications stamp the
import; no registry tracks the placed-on-market pool. That gap is the blind spot
this repository quantifies, from public data only.

---

## Headline findings (annual 2019–2025, UN Comtrade)

| # | Finding | Basis |
|---|---------|-------|
| 1 | **73.7 GWh** of China-origin battery energy entered Australia 2019–2025 (cumulative, trade-derived) | `data/processed/pom_pool.csv` |
| 2 | Inflow went **0.6 → 38.1 GWh/yr** over the period; the pool now roughly **doubles every ~2 years** | `pom_pool.csv` |
| 3 | **2025 alone: ~31.2 GWh / 249.6 kt** of lithium-ion packs (HS 850760) — 82% of the year's pool | `lane_year.csv` |
| 4 | The 2025 basket cost Australia **US$10.2B CIF** (China-reported FOB: US$8.8B) | `lane_year.csv` |
| 5 | Registered installations explain only a fraction of 2025 inflow — **the unregistered surplus is tens of GWh and compounding** | `surplus.csv` |
| 6 | The **storage/swap co-import signature fired in 2025**: packs +202%, inverters/PCS +35%, control cabinets +59% (tonnage, y/y) | `flags.csv` |
| 7 | Mirror ratios are lane-specific diagnostics: lead-acid runs **1.5–1.9×**, Li-ion packs ~1.0–1.2×, e-bikes ~0.9–1.0× | `mirror_ratios.csv` |
| 8 | **Mining-truck tripwire (870410)**: one material arrival event on record — 2021, US$60M / 133 units (propulsion unsplit; under watch) | `flags.csv` |

> Charts below regenerate on every pipeline run. If one has not rendered yet,
> dispatch the workflow once (Actions → *Quarterly refresh* → **Run workflow**)
> — the pipeline commits its own charts.

![Battery energy placed on the Australian market, China-origin](charts/pom_pool.svg)

![Top lanes by Australia-reported CIF value](charts/basket_value.svg)

![Mirror ratios by lane](charts/mirror_ratios.svg)

![Storage/swap co-import signature](charts/coimport_signature.svg)

![Trade inflow vs registered installations](charts/unregistered_surplus.svg)

---

## Why two mirror sides

Every shipment appears twice in UN Comtrade: once as a **China-reported export**
(reporter 156 → partner 36, flow X, FOB value, reliable net weight) and once as
an **Australia-reported import** (reporter 36 → partner 156, flow M, CIF value).
This model pulls both, every period:

- **Tonnage → GWh conversions use the China side** (netWgt is populated there;
  the Australian declaration does not carry usable net weight for these lanes).
- **Value and landed-cost analysis uses the Australian side** (CIF is what the
  Australian market actually pays).
- **The ratio of the two** is a diagnostic: ~1.0–1.2 is normal CIF/FOB lift;
  sustained divergence flags declaration-gap risk (lead-acid 1.84×) or
  misclassification.

## Method in one paragraph

HS lanes, segment mappings and every kg→kWh / kWh-per-unit assumption live in
[`config/hs_lanes.yml`](config/hs_lanes.yml) — config, not code. `src/fetch.py`
pulls both mirror directions from the UN Comtrade API (free key via env secret;
public preview tier works without one). `src/transform.py` builds the per-lane
mirror table, converts battery lanes to GWh, accumulates the placed-on-market
pool, and fires tripwires (mirror-ratio breaks, >50% material moves, 870410
mining-truck arrivals, the 850760+850440+853710 co-import signature).
`src/validate.py` is a hard gate: reproduced totals must sit within ±10% of the
recorded anchors (70.9 GWh cumulative 2019–25; ~31 GWh for 850760 in 2025) or
the run fails and nothing is committed. `src/charts.py` regenerates every chart.
Full methodology and source register: [`docs/method.md`](docs/method.md).

## Reproduce from a fresh clone

```bash
git clone https://github.com/CetaceaCircular/battery-trade-au.git
cd battery-trade-au
pip install -r requirements.txt
python src/fetch.py        # ~15 min on the free public tier; ~1 min with an API key
python src/transform.py
python src/validate.py     # gate: exits 1 if anchors are not reproduced
python src/charts.py
```

No key needed: without `COMTRADE_API_KEY` the fetcher uses UN Comtrade's public
preview endpoint (one period per call, ~100 calls/hour). With a key
([free registration](https://comtradedeveloper.un.org/)) the same script uses
the subscription tier. Keys are read from the environment only — never committed.

## Self-updating

[`.github/workflows/quarterly.yml`](.github/workflows/quarterly.yml) runs the
full pipeline on the 15th of Jan / Apr / Jul / Oct (Sydney morning) and on
manual dispatch: fetch → transform → **validate gate** → commit refreshed CSVs
and charts → open a summary issue listing any tripwires fired in the latest
period (mining-truck arrivals, swap co-import signatures, mirror-ratio breaks).
A failed gate blocks the commit, loudly.

## Repository layout

```
config/hs_lanes.yml        # lane taxonomy, segment maps, conversion assumptions (source of truth)
data/raw/                  # untouched Comtrade API payloads, per period per direction
data/processed/            # lane_year / pom_pool / mirror_ratios / flags / surplus / summary
data/reference/            # bottom-up installation anchors (validation overlay ONLY — never trade data)
src/                       # fetch.py · transform.py · validate.py · charts.py
charts/                    # regenerated every run; Cetacea Deep palette, white field
docs/method.md             # full methodology + source register
.github/workflows/         # quarterly self-update + validation gate
```

## Sources & citations

- **UN Comtrade** (comtradeapi.un.org), annual HS, reporters China (156) and
  Australia (36), flows X/M, HS codes per `config/hs_lanes.yml`. Retrieved per
  the commit date of `data/raw/`.
- Reference overlay (validation only, `data/reference/`): EV Council *State of
  EVs* (2025 BEV/PHEV sales); Clean Energy Regulator CHBP registrations
  (H2-2025 home batteries). See `docs/method.md` §5.
- Calibration anchors recorded from the verified 2026-11 analysis cycle are in
  `config/hs_lanes.yml → anchors` and are **gate targets, not model inputs**.

## Licence

Code: **MIT**. Data and chart outputs: **CC-BY-4.0** — cite
“Cetacea Circular, *battery-trade-au* (UN Comtrade-derived), github.com/CetaceaCircular/battery-trade-au”.
See [LICENSE](LICENSE).
