"""Regenerate all charts from processed tables. Cetacea Deep identity, white field.

Outputs SVG (embedded in README; crisp at any scale) to charts/.
Every chart is regenerated on each pipeline run — never edited by hand.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHARTS, DATA_PROC, PALETTE as P

GRID = dict(axis="y", color=P["mist"], lw=0.8, zorder=0)
SEG_GROUPS = {
    "mixed-large-format": "Large-format packs (850760)",
    "passenger-ev": "Passenger BEV",
    "passenger-phev": "Passenger PHEV",
    "passenger-hybrid": "Passenger hybrid",
    "hybrid-commercial": "Hybrid commercial",
    "bus": "Electric bus",
    "truck": "Electric truck",
    "prime-mover": "Prime mover",
    "forklift-industrial": "Forklift / industrial",
    "e-mobility": "E-mobility",
}
STACK_ORDER = ["Large-format packs (850760)", "Passenger BEV", "Passenger PHEV",
               "Electric bus", "Electric truck", "Prime mover", "Hybrid commercial",
               "Passenger hybrid", "Forklift / industrial", "E-mobility"]
STACK_COLORS = ["#093658", "#2F6C8E", "#5E7280", "#6E8CA0", "#86A3B5",
                "#9FB8C7", "#B9CFDB", "#D3E3EB", "#E3701A", "#C2D5DF"]
# orange deliberately lands on forklift/industrial only if it is ever material;
# the accent that matters is reserved for annotations.


def style(ax, title, kicker):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(P["mist"])
    ax.tick_params(colors=P["steel"], labelsize=9)
    ax.grid(**GRID)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold",
                 color=P["navy"], pad=34)
    ax.text(0, 1.185, kicker.upper(), transform=ax.transAxes, fontsize=8.5,
            color=P["orange"], fontweight="bold")


def save(fig, name):
    CHARTS.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHARTS / f"{name}.svg", bbox_inches="tight", facecolor="white")
    fig.savefig(CHARTS / f"{name}.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  charts/{name}.svg (+png)")


def chart_pool(ly: pd.DataFrame):
    pool = ly[ly.role == "pool"].copy()
    pool["group"] = pool.segment.map(SEG_GROUPS)
    piv = pool.pivot_table(index="year", columns="group", values="gwh",
                           aggfunc="sum").fillna(0)
    piv = piv[[c for c in STACK_ORDER if c in piv.columns]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bottom = pd.Series(0.0, index=piv.index)
    for col, color in zip(piv.columns, STACK_COLORS):
        ax.bar(piv.index, piv[col], bottom=bottom, color=color, width=0.68,
               label=col, zorder=3)
        bottom += piv[col]
    cum = piv.sum(axis=1).cumsum()
    ax.plot(piv.index, cum, color=P["abyss"], lw=1.6, ls="--", zorder=4,
            label="Cumulative pool")
    ax.text(0.99, 1.03, f"{cum.iloc[-1]:.1f} GWh cumulative 2019–{piv.index[-1]}",
            transform=ax.transAxes, ha="right", fontsize=10, fontweight="bold",
            color=P["orange"])
    style(ax, "Battery energy placed on the Australian market, China-origin",
          "POM pool · trade-derived")
    ax.set_ylabel("GWh per year", color=P["steel"], fontsize=9)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.set_xticks(list(piv.index))
    save(fig, "pom_pool")


def chart_mirror(ly: pd.DataFrame):
    core = ["850760", "850440", "853710", "870380", "871160", "850710"]
    labels = {"850760": "850760 Li-ion packs", "850440": "850440 inverters/PCS",
              "853710": "853710 control cabinets", "870380": "870380 BEVs",
              "871160": "871160 e-mobility", "850710": "850710 lead-acid starter"}
    colors = ["#093658", "#2F6C8E", "#5E7280", "#86A3B5", "#B9CFDB", "#E3701A"]
    mr = ly[ly.hs.isin(core) & ly.mirror_ratio.notna()]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for code, color in zip(core, colors):
        g = mr[mr.hs == code].set_index("year").mirror_ratio
        if len(g):
            ax.plot(g.index, g.values, marker="o", ms=3.5, lw=1.6,
                    color=color, label=labels[code], zorder=3)
    ax.axhline(1.0, color=P["steel"], lw=0.9, ls=":")
    ax.text(ly.year.min(), 1.02, "parity (CIF = FOB)", fontsize=8, color=P["steel"])
    style(ax, "Mirror ratio — Australia-reported CIF vs China-reported FOB",
          "Declaration gap · value basis")
    ax.set_ylabel("AU CIF / CN FOB", color=P["steel"], fontsize=9)
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="upper left")
    ax.set_xticks(sorted(ly.year.unique()))
    save(fig, "mirror_ratios")


def chart_basket(ly: pd.DataFrame, latest: int):
    top = (ly[ly.year == latest].nlargest(10, "au_cif_usd")
           .sort_values("au_cif_usd"))
    colors = [P["orange"] if h == "850760" else P["navy"] for h in top.hs]
    labels = [f"{h}  {d[:44].rsplit(' ', 1)[0] if len(d) > 44 else d}"
              for h, d in zip(top.hs, top.desc)]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh(labels, top.au_cif_usd / 1e9, color=colors, zorder=3, height=0.62)
    for i, v in enumerate(top.au_cif_usd / 1e9):
        ax.text(v + 0.05, i, f"{v:.2f}", va="center", fontsize=8.5, color=P["ink"])
    style(ax, f"China-origin basket, Australia-reported CIF value, {latest}",
          "Top 10 lanes · US$ billion")
    ax.set_xlabel("US$ billion CIF", color=P["steel"], fontsize=9)
    ax.grid(axis="x", color=P["mist"], lw=0.8, zorder=0)
    ax.grid(axis="y", visible=False)
    save(fig, "basket_value")


def chart_signature(ly: pd.DataFrame):
    sig = ly[ly.hs.isin(["850760", "850440", "853710"])]
    piv = sig.pivot_table(index="year", columns="hs", values="cn_netwgt_t")
    idx = piv / piv.loc[2022] * 100
    labels = {"850760": "850760 battery packs", "850440": "850440 inverters/PCS",
              "853710": "853710 control cabinets"}
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for code, color in zip(["850760", "850440", "853710"],
                           ["#093658", "#2F6C8E", "#E3701A"]):
        ax.plot(idx.index, idx[code], marker="o", ms=3.5, lw=1.7,
                color=color, label=labels[code], zorder=3)
    style(ax, "Storage / swap co-import signature (tonnage, indexed 2022 = 100)",
          "Co-surge detection")
    ax.set_ylabel("Index", color=P["steel"], fontsize=9)
    ax.legend(fontsize=8.5, frameon=False, loc="upper left")
    ax.set_xticks(list(idx.index))
    save(fig, "coimport_signature")


def chart_surplus():
    path = DATA_PROC / "surplus.csv"
    if not path.exists():
        return
    s = pd.read_csv(path)
    if s.empty:
        return
    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = range(len(s))
    w = 0.38
    ax.bar([i - w / 2 for i in x], s.trade_inflow_gwh, width=w, color=P["navy"],
           label="Trade-derived inflow", zorder=3)
    ax.bar([i + w / 2 for i in x], s.reference_gwh, width=w, color=P["orange"],
           label="Registered installations (EVC · CER · CEC)", zorder=3)
    for i, r in enumerate(s.itertuples()):
        ax.text(i - w / 2, r.trade_inflow_gwh + 0.4, f"{r.trade_inflow_gwh:,.1f}",
                ha="center", fontsize=8, color=P["navy"])
        ax.text(i + w / 2, r.reference_gwh + 0.4, f"{r.reference_gwh:,.1f}",
                ha="center", fontsize=8, color=P["orange"])
    ax.set_xticks(list(x))
    ax.set_xticklabels(
        [f"{r.segment}\n{r.year}" if (pd.isna(r.hs) or not r.hs)
         else f"{r.hs} · {r.segment}\n{r.year}"
         for r in s.itertuples()], fontsize=8)
    style(ax, "Trade inflow vs registered installations",
          "Unallocated inflow · residual = C&I + channel stock + portable + unregistered")
    ax.set_ylabel("GWh", color=P["steel"], fontsize=9)
    ax.legend(fontsize=8.5, frameon=False)
    save(fig, "unallocated_inflow")


def main() -> None:
    ly = pd.read_csv(DATA_PROC / "lane_year.csv", dtype={"hs": str})
    latest = int(ly.year.max())
    chart_pool(ly)
    chart_mirror(ly)
    chart_basket(ly, latest)
    chart_signature(ly)
    chart_surplus()


if __name__ == "__main__":
    main()
