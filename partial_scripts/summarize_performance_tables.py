"""Summarize the SPY-relative tables as mean +/- standard error across seeds.

Example (from the project root):
    module load devel/python/3.13.1
    python partial_scripts/summarize_performance_tables.py

--input accepts the exported CSV or Excel workbook. Excel input uses its numeric
Raw data sheet. Outputs are separate summary PDF, XLSX, CSV and JSON files.
"""

import argparse
import csv
import json
import math
import posixpath
import statistics
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from .export_masterpeng_performance import (
        DEFAULT_ROOT, METHODS, SEEDS, SHEET_NS, STRATEGIES, YEARS,
        col_name, strategy_title, worksheet, write_workbook, xml_bytes,
    )
except ImportError:
    from export_masterpeng_performance import (
        DEFAULT_ROOT, METHODS, SEEDS, SHEET_NS, STRATEGIES, YEARS,
        col_name, strategy_title, worksheet, write_workbook, xml_bytes,
    )


DEFAULT_INPUT = DEFAULT_ROOT / "spy_relative_performance_tables/masterpeng_relative_to_spy.csv"
QUALITY = {
    "above_spy": ("95% CI above zero", "#c9e8d0", 6),
    "below_spy": ("95% CI below zero", "#f2c3c0", 7),
    "unclear": ("95% CI includes zero", "#fff0bd", 8),
    "insufficient": ("Fewer than two results", "#dfe3e8", 9),
}
STAT_FIELDS = ["strategy", "variant", "year", "method", "n", "expected_n",
               "mean_pp", "sample_sd_pp", "sem_pp", "ci95_half_width_pp",
               "ci95_low_pp", "ci95_high_pp", "quality", "mean_buy_trades", "buy_count_n",
               "included_seeds", "missing_seeds"]
NS = {"s": SHEET_NS}
# Two-sided Student-t 95% critical values, df = n - 1. The tables have <=5 seeds.
T95 = {1: 12.706204736432095, 2: 4.302652729696142,
       3: 3.182446305284263, 4: 2.7764451051977987}


def read_table(path):
    """Read numeric seed rows without extracting formatted five-line cells."""
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    if path.suffix.lower() != ".xlsx":
        raise ValueError("Input must be an exported .csv or .xlsx table.")
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        raw = next((s for s in workbook.find("s:sheets", NS)
                    if s.attrib["name"] == "Raw data"), None)
        if raw is None:
            raise ValueError("Excel input has no numeric 'Raw data' sheet.")
        relationship = raw.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        target = next(r.attrib["Target"] for r in rels if r.attrib["Id"] == relationship)
        target = target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(si.itertext())
                      for si in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        sheet = ET.fromstring(archive.read(target))
        grid = []
        for row in sheet.findall("s:sheetData/s:row", NS):
            values = {}
            for cell in row.findall("s:c", NS):
                column = 0
                for letter in cell.attrib["r"].rstrip("0123456789"):
                    column = column * 26 + ord(letter) - ord("A") + 1
                kind = cell.attrib.get("t")
                value = cell.findtext("s:v", default="", namespaces=NS)
                if kind == "s":
                    value = shared[int(value)]
                elif kind == "inlineStr":
                    value = "".join(cell.find("s:is", NS).itertext())
                values[column - 1] = value
            grid.append(values)
        if not grid:
            raise ValueError("The Raw data sheet is empty.")
        headers = grid[0]
        return [{name: row.get(column, "") for column, name in headers.items()}
                for row in grid[1:]]


def seed_statistics(seed_values, seeds=None):
    """Return sample statistics, preserving unavailable standard errors as None."""
    seeds = SEEDS if seeds is None else seeds
    included = sorted(seed_values)
    values = [seed_values[seed] for seed in included]
    if not set(included) <= set(seeds):
        raise ValueError("Unexpected seed in a table cell.")
    if not all(isinstance(value, (float, int)) and math.isfinite(value) for value in values):
        raise ValueError("All included returns must be finite numbers.")
    n = len(values)
    mean = statistics.mean(values) if n else None
    sd = statistics.stdev(values) if n >= 2 else None
    sem = sd / math.sqrt(n) if sd is not None else None
    half_width = T95[n - 1] * sem if sem is not None else None
    low = mean - half_width if half_width is not None else None
    high = mean + half_width if half_width is not None else None
    quality = ("insufficient" if n < 2 else "above_spy" if low > 0
               else "below_spy" if high < 0 else "unclear")
    return {"n": n, "expected_n": len(seeds), "mean_pp": mean, "sample_sd_pp": sd,
            "sem_pp": sem, "ci95_half_width_pp": half_width,
            "ci95_low_pp": low, "ci95_high_pp": high, "quality": quality,
            "included_seeds": included, "missing_seeds": sorted(set(seeds) - set(included))}


def summarize(rows, *, years=None, methods=None, seeds=None):
    """Group only completed seed results; reject duplicate or malformed rows."""
    years = YEARS if years is None else years
    methods = METHODS if methods is None else methods
    seeds = SEEDS if seeds is None else seeds
    method_names = {method for method, _ in methods}
    rows = list(rows)
    has_buys = any("buy_trades" in row for row in rows)
    groups, buy_groups, seen = {}, {}, set()
    for row in rows:
        if row.get("strategy") in {"SP500", "SP500Penguin"}:
            continue
        required = {"year", "method", "seed", "strategy", "variant", "status", "excess_return_pp"}
        if not required <= row.keys():
            raise ValueError("Input must contain SPY-relative seed data, including excess_return_pp and status.")
        base, variant = row["strategy"], int(row["variant"])
        year, method, seed = int(row["year"]), row["method"], int(row["seed"])
        if (base, variant) not in STRATEGIES or year not in years or method not in method_names or seed not in seeds:
            raise ValueError(f"Unexpected table coordinates: {(base, variant, year, method, seed)}")
        key = (base, variant, year, method)
        if (*key, seed) in seen:
            raise ValueError(f"Duplicate seed result: {(*key, seed)}")
        seen.add((*key, seed))
        value = row["excess_return_pp"]
        if row["status"] == "Completed":
            if value in ("", None):
                raise ValueError(f"Completed row has no relative return: {(*key, seed)}")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f"Non-finite relative return: {(*key, seed)}")
            groups.setdefault(key, {})[seed] = value
            if has_buys:
                raw_buys = row.get("buy_trades")
                if raw_buys in ("", None):
                    raise ValueError(f"Completed row has no BUY count: {(*key, seed)}")
                buys = float(raw_buys)
                if not math.isfinite(buys) or buys < 0 or not buys.is_integer():
                    raise ValueError(f"Invalid BUY count: {(*key, seed)}")
                buy_groups.setdefault(key, {})[seed] = int(buys)
        elif value not in ("", None):
            raise ValueError(f"Unfinished row contains a performance value: {(*key, seed)}")
        elif row.get("buy_trades") not in ("", None):
            raise ValueError(f"Unfinished row contains a BUY count: {(*key, seed)}")
    if not seen:
        raise ValueError("Input contains no strategy seed results.")
    stats = []
    for base, variant in STRATEGIES:
        for year in years:
            for method, _ in methods:
                key = (base, variant, year, method)
                buys = buy_groups.get(key, {})
                stats.append({"strategy": base, "variant": variant, "year": year, "method": method,
                              **seed_statistics(groups.get(key, {}), seeds),
                              "mean_buy_trades": statistics.mean(buys.values()) if buys else None,
                              "buy_count_n": len(buys)})
    return stats


def cell_text(stat):
    if stat["mean_pp"] is None:
        value = "No results"
    elif stat["sem_pp"] is None:
        value = f"{stat['mean_pp']:+.2f} ± N/A pp"
    else:
        value = f"{stat['mean_pp']:+.2f} ± {stat['sem_pp']:.2f} pp"
    buys = "N/A" if stat["mean_buy_trades"] is None else f"{stat['mean_buy_trades']:,.1f}"
    return value + f"\nAvg buys: {buys}\nn = {stat['n']}/{stat['expected_n']}"


def styles_xml():
    root = ET.Element("styleSheet", xmlns=SHEET_NS)
    fonts = ET.SubElement(root, "fonts", count="3")
    for size, color, bold in [(11, "17354A", False), (17, "17354A", True), (11, "FFFFFF", True)]:
        font = ET.SubElement(fonts, "font")
        ET.SubElement(font, "sz", val=str(size)); ET.SubElement(font, "name", val="Calibri")
        ET.SubElement(font, "color", rgb="FF" + color)
        if bold:
            ET.SubElement(font, "b")
    fills = ET.SubElement(root, "fills", count="7")
    for pattern in ["none", "gray125"]:
        ET.SubElement(ET.SubElement(fills, "fill"), "patternFill", patternType=pattern)
    for color in ["17354A"] + [info[1].lstrip("#") for info in QUALITY.values()]:
        pattern = ET.SubElement(ET.SubElement(fills, "fill"), "patternFill", patternType="solid")
        ET.SubElement(pattern, "fgColor", rgb="FF" + color.upper())
        ET.SubElement(pattern, "bgColor", indexed="64")
    borders = ET.SubElement(root, "borders", count="2")
    for bordered in [False, True]:
        border = ET.SubElement(borders, "border")
        for side in ["left", "right", "top", "bottom"]:
            line = ET.SubElement(border, side, **({"style": "thin"} if bordered else {}))
            if bordered:
                ET.SubElement(line, "color", rgb="FFD4DEE5")
        ET.SubElement(border, "diagonal")
    ET.SubElement(ET.SubElement(root, "cellStyleXfs", count="1"), "xf",
                  numFmtId="0", fontId="0", fillId="0", borderId="0")
    xfs = ET.SubElement(root, "cellXfs", count="10")
    definitions = [(0, 0, 0, 0), (1, 0, 0, 0), (2, 2, 1, 0), (0, 0, 1, 0),
                   (0, 0, 0, 0), (0, 0, 0, 2)] + [(0, fill, 1, 0) for fill in range(3, 7)]
    for index, (font, fill, border, number) in enumerate(definitions):
        xf = ET.SubElement(xfs, "xf", numFmtId=str(number), fontId=str(font),
                           fillId=str(fill), borderId=str(border), xfId="0", applyAlignment="1")
        ET.SubElement(xf, "alignment", vertical="center", wrapText="1",
                      horizontal="center" if index in [2, 3, 6, 7, 8, 9] else "left")
    ET.SubElement(ET.SubElement(root, "cellStyles", count="1"), "cellStyle",
                  name="Normal", xfId="0", builtinId="0")
    return xml_bytes(root)


def write_xlsx(path, stats, source):
    lookup = {(s["strategy"], s["variant"], s["year"], s["method"]): s for s in stats}
    sheets = []
    for base, variant in STRATEGIES:
        title = strategy_title(base, variant)
        rows = [[(title + " | mean ± SEM vs SPY (pp)", 1)],
                [("Error = sample SD / sqrt(n). Values are strategy return minus the same-run SPY return.", 4)],
                [("Colors use a two-sided 95% Student-t confidence interval, with n - 1 degrees of freedom.", 4)],
                [(QUALITY[name][0], QUALITY[name][2]) for name in QUALITY] + [("Failed seeds excluded; n shown", 4)],
                [("Year", 2)] + [(label, 2) for _, label in METHODS]]
        for year in YEARS:
            row = [(year, 2)]
            for method, _ in METHODS:
                stat = lookup[(base, variant, year, method)]
                row.append((cell_text(stat), QUALITY[stat["quality"]][2]))
            rows.append(row)
        rows.append([("Intervals describe variation across training seeds on shared market data; comparisons are unadjusted.", 4)])
        sheets.append((title.replace(" — variant ", " "), worksheet(
            rows, [13] + [27] * 5, heights={1: 30, 2: 25, 3: 25, 4: 35, 11: 30,
                                         **{r: 74 for r in range(6, 11)}},
            merges=["A1:F1", "A2:F2", "A3:F3", "E4:F4", "A11:F11"],
            freeze=(1, 5), landscape=True)))
    numeric_rows = [[(field, 2) for field in STAT_FIELDS]]
    for stat in stats:
        numeric_rows.append([( ", ".join(map(str, stat[field])) if isinstance(stat[field], list)
                              else stat[field], QUALITY[stat["quality"]][2] if field == "quality"
                              else 5 if field.endswith("_pp") else 0) for field in STAT_FIELDS])
    sheets.append(("Cell statistics", worksheet(numeric_rows, [25, 10, 10, 13, 9, 13] + [21] * (len(STAT_FIELDS) - 6),
                                                freeze=(0, 1), autofilter=f"A1:{col_name(len(STAT_FIELDS))}{len(numeric_rows)}")))
    notes = ["SPY-relative performance: seed averages and statistical errors",
             "Cell values are mean ± SEM, in percentage points. SEM = sample SD / sqrt(n), with SD using n - 1.",
             "95% CI = mean ± t(0.975, n - 1) × SEM. Confidence intervals are separate from the displayed ± SEM.",
             "Green: CI above zero. Red: CI below zero. Amber: CI includes zero. Gray: fewer than two seed results.",
             "Failed and absent seeds are excluded, never replaced by zeros. A one-seed cell has no estimable SEM or CI.",
             "Avg buys = average executed test BUY orders across the same completed seeds used for returns.",
             "These are seed-level, unadjusted intervals on shared test market data; they do not describe variation across market periods.",
             "Variant 1: original name without a numeric suffix. Variant 2: original name with a numeric suffix.",
             "SPY is a reference benchmark only; no separate SP500 evaluation is produced.",
             "Numeric cell statistics and included/missing seeds are saved in the Cell statistics sheet and companion CSV/JSON.",
             "Input table: " + str(source), "Generated (UTC): " + datetime.now(timezone.utc).isoformat()]
    sheets.append(("Read me", worksheet([[(note, 1 if i == 0 else 4)] for i, note in enumerate(notes)],
                                        [150], heights={i: 36 for i in range(1, len(notes) + 1)})))
    write_workbook(path, sheets, styles_xml())


def write_pdf(path, stats):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Patch
    lookup = {(s["strategy"], s["variant"], s["year"], s["method"]): s for s in stats}
    with PdfPages(path) as pdf:
        for page, (base, variant) in enumerate(STRATEGIES, 1):
            figure, axis = plt.subplots(figsize=(14, 9))
            figure.patch.set_facecolor("white"); axis.axis("off")
            figure.text(0.055, 0.945, strategy_title(base, variant), color="#17354a", fontsize=23, weight="bold")
            figure.text(0.055, 0.905, "Mean excess return vs SPY ± standard error (pp) | start year × search method",
                        color="#43596a", fontsize=12)
            values = [[str(year)] + [cell_text(lookup[(base, variant, year, method)])
                                     for method, _ in METHODS] for year in YEARS]
            table = axis.table(cellText=values, colLabels=["Year"] + [label for _, label in METHODS],
                               cellLoc="center", colWidths=[0.07] + [0.186] * 5, bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False); table.set_fontsize(12)
            for (row, column), cell in table.get_celld().items():
                cell.set_edgecolor("#d4dee5"); cell.set_linewidth(0.8)
                if row == 0 or column == 0:
                    cell.set_facecolor("#17354a"); cell.set_text_props(color="white", weight="bold")
                else:
                    stat = lookup[(base, variant, YEARS[row - 1], METHODS[column - 1][0])]
                    cell.set_facecolor(QUALITY[stat["quality"]][1])
                    cell.get_text().set_linespacing(1.3)
                cell.set_height(0.07 if row == 0 else 0.186)
            axis.set_position([0.055, 0.23, 0.89, 0.62])
            figure.legend(handles=[Patch(facecolor=color, edgecolor="#b0bac3", label=label)
                                   for label, color, _ in QUALITY.values()],
                          loc="lower center", bbox_to_anchor=(0.5, 0.155), ncol=4, frameon=False, fontsize=10)
            figure.text(0.055, 0.12, "SEM = sample SD / √n. Colors use mean ± t(0.975, n−1) × SEM, a 95% confidence interval.",
                        fontsize=10, color="#43596a")
            figure.text(0.055, 0.09, "Failed seeds excluded; n = available / 5. Intervals describe seed variation on shared market data; comparisons are unadjusted.",
                        fontsize=9, color="#43596a")
            figure.text(0.055, 0.06, "Avg buys = executed test BUY orders averaged across the included seeds. Positive returns mean outperformance of SPY.",
                        fontsize=9, color="#43596a")
            figure.text(0.945, 0.03, f"{page} / {len(STRATEGIES)}", ha="right", fontsize=9, color="#43596a")
            pdf.savefig(figure)
            if page == 1:
                figure.savefig(path.with_name("preview_summary_emperor_1.png"), dpi=140)
            plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Seed-level CSV or XLSX table export.")
    parser.add_argument("--output-dir", type=Path, help="Default: a summary subdirectory beside the input table.")
    parser.add_argument("--skip-pdf", action="store_true", help="Write XLSX/CSV/JSON without needing matplotlib.")
    args = parser.parse_args()
    source = args.input.expanduser().resolve()
    stats = summarize(read_table(source))
    output = args.output_dir.expanduser().resolve() if args.output_dir else source.parent / "summary"
    output.mkdir(parents=True, exist_ok=True)
    stem = output / "masterpeng_relative_to_spy_summary"
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=STAT_FIELDS)
        writer.writeheader()
        writer.writerows({key: ",".join(map(str, value)) if isinstance(value, list) else value
                          for key, value in stat.items()} for stat in stats)
    metadata = {"input": str(source), "display": "mean ± sample standard error, in percentage points",
                "standard_error": "sample SD (ddof=1) / sqrt(n)",
                "average_buys": "mean executed test BUY orders across the same included seeds as returns",
                "confidence_interval": "two-sided 95% Student-t, df=n-1; unadjusted across comparisons",
                "quality_legend": {key: {"label": value[0], "color": value[1]} for key, value in QUALITY.items()},
                "generated_at_utc": datetime.now(timezone.utc).isoformat(), "cells": stats}
    stem.with_suffix(".json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n")
    write_xlsx(stem.with_suffix(".xlsx"), stats, source)
    if not args.skip_pdf:
        write_pdf(stem.with_suffix(".pdf"), stats)
    print(json.dumps({"output": str(output), "tables": len(STRATEGIES), "cells": len(stats),
                      "quality_counts": dict(Counter(stat["quality"] for stat in stats)),
                      "sample_sizes": dict(Counter(stat["n"] for stat in stats))}, indent=2))


if __name__ == "__main__":
    main()
