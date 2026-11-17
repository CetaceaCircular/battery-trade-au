# charts

All charts are generated artifacts — never edited by hand. `src/charts.py`
rebuilds every SVG on each pipeline run (locally and in CI), in the Cetacea
Deep palette on a white field. PNG review copies are written alongside but are
git-ignored; the repo tracks SVG only (text-diffable, renders natively on
GitHub).

If this folder is empty, run the pipeline (README §Reproduce) or dispatch the
quarterly workflow — the charts commit themselves.
