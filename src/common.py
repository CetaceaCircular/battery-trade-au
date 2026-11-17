"""Shared helpers: paths, config loading, Cetacea Deep palette."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "hs_lanes.yml"
DATA_RAW = ROOT / "data" / "raw"
DATA_PROC = ROOT / "data" / "processed"
DATA_REF = ROOT / "data" / "reference"
CHARTS = ROOT / "charts"

# Cetacea Deep visual identity (locked 2026-11-17). Do not add hues.
PALETTE = {
    "navy": "#093658",    # primary series
    "abyss": "#06253D",   # deepest series / cumulative line
    "ocean": "#2F6C8E",   # secondary series
    "mist": "#DCE9F0",    # gridlines, minor series
    "ice": "#F2F7FA",     # panels
    "ink": "#10293A",     # text
    "steel": "#5E7280",   # secondary text
    "orange": "#E3701A",  # the ONLY accent — the number that matters
}
SERIES_ORDER = ["#093658", "#2F6C8E", "#5E7280", "#8FA8B8", "#C2D5DF", "#06253D"]


def load_config() -> dict:
    with open(CONFIG, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def lanes(cfg: dict) -> list[dict]:
    return cfg["lanes"]


def lane_codes(cfg: dict) -> list[str]:
    return [str(l["hs"]) for l in cfg["lanes"]]
