"""Reports into README tables and SVG charts. Every number in the README is written here from `reports/`."""
from __future__ import annotations

import json
import math

from imdh.eval.run import CAUSE_ORDER, ORDER, ROOT

LABELS = {
    "single_vendor": "One vendor (Northwind)",
    "primary_backup": "Primary with backup",
    "median_consensus": "Median of three vendors",
    "hub_no_desk": "Hub, no desk lookups",
    "hub_unranked_desk": "Hub, desk in id order",
    "hub_no_action_check": "Hub, no action checks",
    "hub_no_stale_or_unit_check": "Hub, no stale or unit checks",
    "hub_undated_symbology": "Hub, undated identifiers",
    "hub": "**Hub**",
}
START, END = "<!-- results:start -->", "<!-- results:end -->"

# light-mode reference palette (dataviz skill), slots 1-3 and neutrals
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
SERIES = {"hub": "#2a78d6", "single_vendor": "#eb6834", "median_consensus": "#1baf7a"}
NEUTRAL_BAR = "#b9b8b3"


def load(name: str) -> dict | None:
    p = ROOT / "reports" / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def unpublished(d: dict) -> int:
    """Index-days whose level could not be calculated. The first held-out scorer did not count these (they compared
    as not wrong); they are recovered from the daily series. A level can only become uncalculable on the base date,
    where it then shows as zero wrong closes and a zero worst error for that index, so designs without a series
    and with errors on every index had none."""
    if "unpublished_index_days" in d:
        return d["unpublished_index_days"]
    series = d.get("daily_error_bps") or {}
    return sum(1 for v in series.values() for x in v if x is None or x != x)


def _design_table(r: dict) -> list[str]:
    rows = ["| Design | Index closes wrong or not calculable | Still wrong after next-morning restatement | "
            "Worst index error | Wrong golden prices | Wrong corporate actions | Desk lookups |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for name in ORDER:
        d = r["designs"][name]
        bold = name == "hub"
        missing = unpublished(d)
        closes = d["wrong_index_closes"] + (0 if "unpublished_index_days" in d else missing)
        closes_txt = f"{closes} ({missing} not calculable)" if missing else str(closes)
        cells = [closes_txt, d["wrong_after_restatement"] + (0 if "unpublished_index_days" in d else missing),
                 f"{d['max_index_error_bps']:,.1f} bp", d["wrong_prices"], d["wrong_actions"], d["desk_lookups"]]
        cells = [f"**{c}**" if bold else str(c) for c in cells]
        rows.append(f"| {LABELS[name]} | " + " | ".join(cells) + " |")
    return rows


def _cause_table(r: dict) -> list[str]:
    names = ["single_vendor", "median_consensus", "hub_no_desk", "hub"]
    rows = ["| Why a golden price was wrong | " + " | ".join(LABELS[n].strip("*") for n in names) + " |",
            "|---|" + "---:|" * len(names)]
    nice = {"late_file": "vendor file after the close", "missing": "quote missing", "stale": "repeated price",
            "spike": "bad tick", "unit_label": "pence labelled as pounds", "rename": "rename or reused ticker",
            "other": "other"}
    for c in CAUSE_ORDER:
        rows.append(f"| {nice[c]} | " + " | ".join(str(r["designs"][n]["wrong_prices_by_cause"][c])
                                                  for n in names) + " |")
    return rows


def _actions_table(r: dict) -> list[str]:
    names = ["single_vendor", "median_consensus", "hub_no_action_check", "hub"]
    rows = ["| Corporate actions on constituents | " + " | ".join(LABELS[n].strip("*") for n in names) + " |",
            "|---|" + "---:|" * len(names)]
    for k, label in (("missed", "missed"), ("wrong_date", "applied on the wrong day"),
                     ("wrong_value", "wrong ratio or amount"), ("phantom", "applied but never happened")):
        rows.append(f"| {label} | " + " | ".join(str(r["designs"][n]["actions"][k]) for n in names) + " |")
    return rows


def readme_block() -> str:
    dev, held = load("dev"), load("heldout")
    w = dev["world"]
    hub, single, median = (dev["designs"][k] for k in ("hub", "single_vendor", "median_consensus"))
    lines = [START, "",
             f"**Development market** (seed {w['seed']}, {w['first_day']} to {w['last_day']}): {w['business_days']} "
             f"business days, {w['instruments']} instruments, {len(w['indices'])} indices with {w['constituents']} "
             f"constituents, {w['quotes']:,} vendor quotes, {w['late_vendor_days']} vendor-days delivered after the "
             f"close, {sum(w['corporate_actions'].values())} corporate actions and {w['renames']} renames on "
             f"constituents ({w['ticker_reuses']} tickers reused).",
             "",
             "| | One vendor | Median of three | **Hub** |",
             "|---|---:|---:|---:|",
             f"| Index closes off the true level by more than 1 bp (of {hub['index_days']}) | "
             f"{single['wrong_index_closes']} | {median['wrong_index_closes']} | **{hub['wrong_index_closes']}** |",
             f"| Worst index error | {single['max_index_error_bps']:,.1f} bp | {median['max_index_error_bps']:,.1f} bp "
             f"| **{hub['max_index_error_bps']:,.1f} bp** |",
             f"| Corporate actions missed or misapplied (of {hub['actions']['true']}) | {single['wrong_actions']} | "
             f"{median['wrong_actions']} | **{hub['wrong_actions']}** |",
             f"| Desk lookups over the quarter | 0 | 0 | **{hub['desk_lookups']}** "
             f"({hub['desk_minutes']:.0f} min) |",
             "", "![Index closes off the truth, by design](reports/charts/wrong_closes.svg)", "",
             "![Daily index error, UK Select 20](reports/charts/daily_error.svg)", "",
             "<details><summary>Every design on the development market</summary>", "", *_design_table(dev), "",
             *_cause_table(dev), "", *_actions_table(dev), "", "</details>", ""]
    gate = dev["gate"]
    lines.append(f"Gate on the development market: **{'passed' if gate['passed'] else 'failed'}** ("
                 + ", ".join(f"{k.replace('_', ' ')} {v['value']} of at most {v['limit']}"
                             for k, v in gate["checks"].items())
                 + f"). The product calculator and the world's own engine agree to {dev['calculators_agree']:.1e} "
                 "on the true market.")
    lines.append("")
    if held:
        hw, hh = held["world"], held["designs"]
        lines += ["**Held-out market, first and only run** "
                  f"(seed {hw['seed']}, {hw['first_day']} to {hw['last_day']}, {hw['instruments']} instruments, "
                  f"{hw['late_vendor_days']} late vendor-days, {sum(hw['corporate_actions'].values())} corporate "
                  f"actions, {hw['renames']} renames, {hw['ticker_reuses']} reused tickers):", "",
                  *_design_table(held), "",
                  f"Hub gate on the held-out market: **{'passed' if held['gate']['passed'] else 'failed'}**. "
                  "What it got wrong is written up in [docs/heldout.md](docs/heldout.md).", ""]
        _ = hh
    else:
        lines += ["The held-out market has not been run yet.", ""]
    lines.append(END)
    return "\n".join(lines)


def write_readme(check: bool = False) -> bool:
    path = ROOT / "README.md"
    text = path.read_text()
    a, b = text.index(START), text.index(END) + len(END)
    new = text[:a] + readme_block() + text[b:]
    if check:
        return new == text
    path.write_text(new)
    return True


def _svg(w: int, h: int, body: str, title: str, desc: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="t d" font-family="Inter, Segoe UI, sans-serif">\n<title id="t">{title}</title>'
            f'<desc id="d">{desc}</desc>\n<rect width="{w}" height="{h}" fill="{SURFACE}"/>\n{body}\n</svg>\n')


def chart_wrong_closes(r: dict) -> str:
    names = ORDER
    W, row, left, top = 760, 30, 230, 56
    H = top + row * len(names) + 40
    vmax = max(r["designs"][n]["wrong_index_closes"] for n in names) or 1
    x = lambda v: left + (W - left - 70) * v / vmax  # noqa: E731
    parts = [f'<text x="16" y="26" font-size="15" font-weight="700" fill="{INK}">Index closes off the true level by '
             f'more than 1 bp</text>',
             f'<text x="16" y="44" font-size="12" fill="{MUTED}">Development market, '
             f'{r["designs"]["hub"]["index_days"]} index-days, same vendor files for every design</text>']
    for k, n in enumerate(names):
        v = r["designs"][n]["wrong_index_closes"]
        y = top + k * row
        fill = SERIES["hub"] if n == "hub" else NEUTRAL_BAR
        weight = 700 if n == "hub" else 400
        parts.append(f'<text x="{left - 10}" y="{y + 18}" text-anchor="end" font-size="12" font-weight="{weight}" '
                     f'fill="{INK}">{LABELS[n].strip("*")}</text>')
        width = max(x(v) - left, 2)
        parts.append(f'<rect x="{left}" y="{y + 6}" width="{width:.1f}" height="16" rx="4" fill="{fill}"/>')
        parts.append(f'<text x="{left + width + 6:.1f}" y="{y + 18}" font-size="12" font-weight="{weight}" '
                     f'fill="{INK}">{v}</text>')
    return _svg(W, H, "\n".join(parts), "Index closes off the true level by design",
                "Horizontal bars: wrong index closes per design on the development market.")


def chart_daily_error(r: dict, index: str = "UKS20") -> str:
    W, H, lft, rt, t, b = 760, 340, 64, 150, 56, 44
    names = ["single_vendor", "median_consensus", "hub"]
    floor = 0.01
    series = {n: [max(e, floor) for e in r["designs"][n]["daily_error_bps"][index]] for n in names}
    n_days = len(series["hub"])
    top = 10 ** math.ceil(math.log10(max(max(v) for v in series.values())))
    y = lambda v: t + (H - t - b) * (math.log10(top) - math.log10(v)) / (math.log10(top) - math.log10(floor))  # noqa: E731
    x = lambda k: lft + (W - lft - rt) * k / (n_days - 1)  # noqa: E731
    parts = [f'<text x="16" y="26" font-size="15" font-weight="700" fill="{INK}">Daily error of the published '
             f'close, {index}</text>',
             f'<text x="16" y="44" font-size="12" fill="{MUTED}">Basis points off the true level, log scale; '
             f'below 0.01 bp drawn at 0.01</text>']
    v = floor
    while v <= top * 1.0001:
        parts.append(f'<line x1="{lft}" x2="{W - rt}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}"/>')
        label = f"{v:g}"
        parts.append(f'<text x="{lft - 8}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="11" '
                     f'fill="{MUTED}">{label}</text>')
        v *= 10
    one = y(1.0)
    parts.append(f'<line x1="{lft}" x2="{W - rt}" y1="{one:.1f}" y2="{one:.1f}" stroke="{MUTED}" '
                 f'stroke-dasharray="4 4"/>')
    for k in range(0, n_days, 10):
        parts.append(f'<text x="{x(k):.1f}" y="{H - b + 18}" text-anchor="middle" font-size="11" '
                     f'fill="{MUTED}">day {k + 1}</text>')
    for n in names:
        pts = " ".join(f"{x(k):.1f},{y(e):.1f}" for k, e in enumerate(series[n]))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{SERIES[n]}" stroke-width="2" '
                     f'stroke-linejoin="round"/>')
    ends = sorted((y(series[n][-1]), n) for n in names)
    last = -99.0
    for yy, n in ends:
        yy = max(yy, last + 16)
        last = yy
        parts.append(f'<text x="{W - rt + 8}" y="{yy + 4:.1f}" font-size="12" fill="{INK}">'
                     f'{LABELS[n].strip("*")}</text>')
    parts.append(f'<text x="{W - rt - 4}" y="{one - 6:.1f}" text-anchor="end" font-size="11" fill="{MUTED}">'
                 f'1 bp</text>')
    return _svg(W, H, "\n".join(parts), f"Daily index error for {index}",
                "Three lines on a log scale: one vendor, median of three and the hub.")


def write_charts() -> None:
    dev = load("dev")
    out = ROOT / "reports" / "charts"
    out.mkdir(parents=True, exist_ok=True)
    (out / "wrong_closes.svg").write_text(chart_wrong_closes(dev))
    (out / "daily_error.svg").write_text(chart_daily_error(dev))
