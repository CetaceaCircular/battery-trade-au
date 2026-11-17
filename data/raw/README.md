# data/raw

Untouched UN Comtrade API payloads, one JSON per period per mirror direction:
`comtrade_{cn_export|au_import}_{year}.json`.

This directory is populated by every `src/fetch.py` run (local or CI). Raw
payloads from scheduled runs are committed by the quarterly workflow so each
processed figure diffs back to an immutable upstream record. The initial
bootstrap commit ships processed outputs only — run `python src/fetch.py` to
materialise the raw layer (free public tier, no key required).
