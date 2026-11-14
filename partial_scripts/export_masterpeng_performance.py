"""Export MasterPeng returns as separate 5 x 5 tables for each strategy variant.

Run with the cluster Python module for PDF output:
    module load devel/python/3.13.1
    python partial_scripts/export_masterpeng_performance.py
    python partial_scripts/export_masterpeng_performance.py --relative-to-spy

The XLSX and CSV writers use only the standard library. PDF output uses matplotlib.
SPY is used only as a benchmark; it never gets its own evaluation table.
"""

import argparse
import csv
import json
import math
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = PROJECT / "run_log" / "MasterPeng_ALL_RUNS_TC1.0_TS500"
YEARS = list(range(2020, 2025))
SEEDS = [11, 22, 33, 42, 55]
METHODS = [("random", "Random"), ("cmaes", "CMA-ES"), ("tpe", "TPE"),
           ("gpei", "GP-EI"), ("gpucb", "GP-UCB")]
STRATEGIES = [(base, variant) for base in
              ["EmperorPenguin", "GentooPenguin", "RockhopperPenguin"]
              for variant in [1, 2]]
FIELDS = ["year", "method", "seed", "strategy", "variant", "original_strategy_name",
          "return_pct", "spy_return_pct", "excess_return_pp", "total_return",
          "max_drawdown", "sharpe_ratio", "final_value",
          "status", "failure", "source_file"]
NUMERIC_FIELDS = {"return_pct", "spy_return_pct", "excess_return_pp", "total_return",
                  "max_drawdown", "sharpe_ratio", "final_value"}
SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def strategy_title(base, variant):
    return "{} — variant {}".format(
        base.replace("Penguin", ""), variant)


def collect(root):
    records, failures, run_counts = [], [], Counter()
    for year in YEARS:
        for method, _ in METHODS:
            for seed in SEEDS:
                name = "MR_{}_broad_{}_500_RS_{}".format(year, method, seed)
                run = root / "Year{}".format(year) / "RS_{}".format(seed) / name
                metrics_path = run / "artifacts/json/metrics_summary.json"
                metrics = json.loads(metrics_path.read_text()) if metrics_path.is_file() else None
                error = ""
                if metrics is None:
                    log_root = PROJECT.parent / "slurm_scripts/logs_multi_start" / root.name
                    logs = list((log_root / run.parent.relative_to(root)).glob(
                        "sim_lr_{}_*.out".format(name)))
                    for log in logs:
                        matches = re.findall(r"^(?:RuntimeError|TypeError): .+$",
                                             log.read_text(errors="replace"), re.MULTILINE)
                        if matches:
                            error = matches[-1]
                    error = error or "Final performance metrics are missing."
                    failures.append({"year": year, "method": method, "seed": seed,
                                     "run": name, "failure": error})
                else:
                    for filename in ["report.pdf", "TrainingPareto.pdf",
                                     "ValidationPareto.pdf", "Param_Evo.pdf"]:
                        if not (run / filename).is_file():
                            raise ValueError("Missing final output: {}".format(run / filename))
                status = "Completed" if metrics is not None else "Failed"
                run_counts[status] += 1
                spy_return = None
                if metrics is not None:
                    spy_return = metrics.get("SP500", {}).get("return_pct")
                    if not isinstance(spy_return, (int, float)) or not math.isfinite(spy_return):
                        raise ValueError("Invalid SPY benchmark return in {}".format(metrics_path))
                variants = {}
                for original, values in (metrics or {}).items():
                    if original == "SP500":
                        continue
                    match = re.fullmatch(
                        r"(EmperorPenguin|GentooPenguin|RockhopperPenguin)(?:_(\d+))?",
                        original)
                    if not match:
                        raise ValueError("Unexpected strategy name: {}".format(original))
                    key = (match.group(1), 2 if match.group(2) else 1)
                    if key in variants:
                        raise ValueError("Duplicate variant {} in {}".format(key, run))
                    variants[key] = (original, values)
                if metrics is not None and set(variants) != set(STRATEGIES):
                    raise ValueError("Unexpected strategy coverage in {}".format(run))
                for base, variant in STRATEGIES:
                    original, values = variants.get((base, variant), ("", {}))
                    record = dict(year=year, method=method, seed=seed, strategy=base,
                                  variant=variant, original_strategy_name=original,
                                  status=status, failure=error, source_file=str(metrics_path))
                    for field in ["return_pct", "total_return", "max_drawdown",
                                  "sharpe_ratio", "final_value"]:
                        value = values.get(field)
                        if metrics is not None and (not isinstance(value, (int, float))
                                                    or not math.isfinite(value)):
                            raise ValueError("Invalid {} in {}".format(field, metrics_path))
                        record[field] = value
                    record["spy_return_pct"] = spy_return
                    record["excess_return_pp"] = (round(record["return_pct"] - spy_return, 2)
                                                  if metrics is not None else None)
                    records.append(record)
    return records, failures, dict(run_counts)


def cell_text(records, year, method, base, variant, relative_to_spy=False):
    lines = []
    for seed in SEEDS:
        record = records[(year, method, seed, base, variant)]
        value = record["excess_return_pp" if relative_to_spy else "return_pct"]
        suffix = " pp" if relative_to_spy else "%"
        lines.append("RS {}: {}".format(seed, "FAILED" if value is None
                                         else "{:+.2f}{}".format(value, suffix)))
    return "\n".join(lines)


def col_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml_bytes(element):
    return ET.tostring(element, encoding="utf-8", xml_declaration=True)


def worksheet(rows, widths, heights=None, merges=(), freeze=None, autofilter=None,
              landscape=False):
    def tag(name):
        return "{{{}}}{}".format(SHEET_NS, name)
    sheet = ET.Element(tag("worksheet"))
    view = ET.SubElement(ET.SubElement(sheet, tag("sheetViews")), tag("sheetView"),
                         workbookViewId="0", showGridLines="0")
    if freeze:
        x, y = freeze
        ET.SubElement(view, tag("pane"), xSplit=str(x), ySplit=str(y),
                      topLeftCell="{}{}".format(col_name(x + 1), y + 1),
                      activePane="bottomRight" if x else "bottomLeft", state="frozen")
    ET.SubElement(sheet, tag("sheetFormatPr"), defaultRowHeight="18")
    cols = ET.SubElement(sheet, tag("cols"))
    for i, width in enumerate(widths, 1):
        ET.SubElement(cols, tag("col"), min=str(i), max=str(i),
                      width=str(width), customWidth="1")
    data = ET.SubElement(sheet, tag("sheetData"))
    for row_number, row in enumerate(rows, 1):
        attributes = {"r": str(row_number)}
        if heights and row_number in heights:
            attributes.update(ht=str(heights[row_number]), customHeight="1")
        row_element = ET.SubElement(data, tag("row"), attributes)
        for column, item in enumerate(row, 1):
            value, style = item if isinstance(item, tuple) else (item, 0)
            if value is None:
                continue
            cell = ET.SubElement(row_element, tag("c"),
                                 r="{}{}".format(col_name(column), row_number), s=str(style))
            if isinstance(value, (int, float)):
                ET.SubElement(cell, tag("v")).text = str(value)
            else:
                cell.set("t", "inlineStr")
                text = ET.SubElement(ET.SubElement(cell, tag("is")), tag("t"))
                text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                text.text = str(value)
    if autofilter:
        ET.SubElement(sheet, tag("autoFilter"), ref=autofilter)
    if merges:
        merged = ET.SubElement(sheet, tag("mergeCells"), count=str(len(merges)))
        for ref in merges:
            ET.SubElement(merged, tag("mergeCell"), ref=ref)
    ET.SubElement(sheet, tag("pageMargins"), left="0.25", right="0.25", top="0.35",
                  bottom="0.35", header="0.15", footer="0.15")
    if landscape:
        ET.SubElement(sheet, tag("pageSetup"), paperSize="9", orientation="landscape",
                      fitToWidth="1", fitToHeight="1")
    return xml_bytes(sheet)


def write_xlsx(path, records, lookup, failures, counts, relative_to_spy=False,
               root=DEFAULT_ROOT):
    sheets = []
    metric_label = "excess return vs SPY (pp)" if relative_to_spy else "test return (%)"
    explanation = ("Strategy test return (%) minus SPY test return (%). "
                   "Positive = outperformance; negative = underperformance."
                   if relative_to_spy else "Values are saved test returns (%), not annualized.")
    for base, variant in STRATEGIES:
        title = strategy_title(base, variant)
        rows = [[(title + " | " + metric_label, 1)],
                [("Rows: start year | columns: search method | five seed results per cell", 4)],
                [("Variant 1: original name without suffix. Variant 2: original name with numeric suffix.", 4)],
                [("Seed order: 11, 22, 33, 42, 55. FAILED means no final test result; it is not zero.", 4)],
                [("Year", 2)] + [(label, 2) for _, label in METHODS]]
        for year in YEARS:
            row = [(year, 2)]
            for method, _ in METHODS:
                value = cell_text(lookup, year, method, base, variant, relative_to_spy)
                row.append((value, 6 if "FAILED" in value else 3))
            rows.append(row)
        rows.append([(explanation, 4)])
        sheets.append((title.replace(" — variant ", " "), worksheet(
            rows, [12] + [26] * 5, heights={1: 30, 2: 24, 3: 24, 4: 24, 11: 30,
                                         **{i: 96 for i in range(6, 11)}},
            merges=["A1:F1", "A2:F2", "A3:F3", "A4:F4", "A11:F11"],
            freeze=(1, 5), landscape=True)))
    raw_rows = [[(field, 2) for field in FIELDS]]
    for record in records:
        raw_rows.append([(record[field], 5 if field in NUMERIC_FIELDS else 0)
                         for field in FIELDS])
    widths = {"year": 10, "method": 12, "seed": 9, "strategy": 25, "variant": 9,
              "original_strategy_name": 30, "status": 14, "failure": 70, "source_file": 80}
    sheets.append(("Raw data", worksheet(raw_rows, [widths.get(field, 18) for field in FIELDS],
                                         freeze=(0, 1), autofilter="A1:{}{}".format(
                                             col_name(len(FIELDS)), len(raw_rows)))))
    failure_fields = ["year", "method", "seed", "run", "failure"]
    failure_rows = [[(field, 2) for field in failure_fields]] + [
        [(record[field], 4) for field in failure_fields] for record in failures]
    sheets.append(("Failed runs", worksheet(failure_rows, [10, 12, 9, 42, 100],
                                             heights={i: 72 for i in range(2, len(failures) + 2)},
                                             freeze=(0, 1))))
    about = [
        "MasterPeng performance tables" + (" relative to SPY" if relative_to_spy else ""),
        "5 start years × 5 search methods; five random seed returns in each cell.",
        explanation,
        "Performance is from the saved test results; not annualized or training performance.",
        "Variant 1 = strategy name without numeric suffix. Variant 2 = strategy name with numeric suffix.",
        "Numeric suffixes are original trial identifiers and are preserved in the Raw data sheet.",
        "SPY reference = saved SP500 buy-and-hold return from the same run; there is no separate benchmark evaluation.",
        "Seed order: 11, 22, 33, 42, 55. Failed results are blank in Raw data and CSV, never zero.",
        "Completed: {} / 125; failed: {} / 125.".format(counts.get("Completed", 0), counts.get("Failed", 0)),
        "Raw data return_pct and max_drawdown use percentage units, e.g. -45.18 means -45.18%.",
        "Raw data spy_return_pct is the SPY reference; excess_return_pp = return_pct - spy_return_pct (percentage points).",
        "Source: */artifacts/json/metrics_summary.json in " + str(root),
        "Generated (UTC): " + datetime.now(timezone.utc).isoformat(),
    ]
    sheets.append(("Read me", worksheet([[(line, 1 if i == 0 else 4)]
                                         for i, line in enumerate(about)], [145],
                                        heights={i: 34 for i in range(1, len(about) + 1)})))
    styles = '''<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="16"/><name val="Calibri"/><color rgb="FF17354A"/></font><font><b/><sz val="11"/><name val="Calibri"/><color rgb="FFFFFFFF"/></font><font><sz val="11"/><name val="Consolas"/></font></fonts>
<fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF17354A"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF1F5F8"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFFFF1DC"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFD4DEE5"/></left><right style="thin"><color rgb="FFD4DEE5"/></right><top style="thin"><color rgb="FFD4DEE5"/></top><bottom style="thin"><color rgb="FFD4DEE5"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="7"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf><xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
    write_workbook(path, sheets, styles)


def write_workbook(path, sheets, styles):
    """Package worksheet XML and styles into an Excel workbook."""
    package_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
    workbook = ET.Element("workbook", xmlns=SHEET_NS)
    sheet_nodes = ET.SubElement(workbook, "sheets")
    rels = ET.Element("Relationships", xmlns=package_ns)
    content = ET.Element("Types", xmlns=ct_ns)
    ET.SubElement(content, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    ET.SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(content, "Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    ET.SubElement(content, "Override", PartName="/xl/styles.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for i, (name, data) in enumerate(sheets, 1):
            ET.SubElement(sheet_nodes, "sheet", name=name, sheetId=str(i),
                          attrib={"{{{}}}id".format(REL_NS): "rId{}".format(i)})
            ET.SubElement(rels, "Relationship", Id="rId{}".format(i),
                          Type=REL_NS + "/worksheet", Target="worksheets/sheet{}.xml".format(i))
            ET.SubElement(content, "Override", PartName="/xl/worksheets/sheet{}.xml".format(i),
                          ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
            archive.writestr("xl/worksheets/sheet{}.xml".format(i), data)
        ET.SubElement(rels, "Relationship", Id="rId{}".format(len(sheets) + 1),
                      Type=REL_NS + "/styles", Target="styles.xml")
        root_rels = ET.Element("Relationships", xmlns=package_ns)
        ET.SubElement(root_rels, "Relationship", Id="rId1", Type=REL_NS + "/officeDocument", Target="xl/workbook.xml")
        archive.writestr("[Content_Types].xml", xml_bytes(content))
        archive.writestr("_rels/.rels", xml_bytes(root_rels))
        archive.writestr("xl/workbook.xml", xml_bytes(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", xml_bytes(rels))
        archive.writestr("xl/styles.xml", styles)


def write_pdf(path, lookup, counts, relative_to_spy=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    with PdfPages(path) as pdf:
        for page, (base, variant) in enumerate(STRATEGIES, 1):
            fig, ax = plt.subplots(figsize=(14, 9))
            fig.patch.set_facecolor("white")
            ax.axis("off")
            fig.text(0.055, 0.945, strategy_title(base, variant), fontsize=23,
                     color="#17354a", weight="bold")
            metric_label = "Excess return vs SPY (pp)" if relative_to_spy else "Test return (%)"
            fig.text(0.055, 0.908, metric_label + " | start year × search method | five seed results per cell",
                     fontsize=12, color="#43596a")
            contents = [[str(year)] + [cell_text(lookup, year, method, base, variant, relative_to_spy)
                                       for method, _ in METHODS] for year in YEARS]
            table = ax.table(cellText=contents, colLabels=["Year"] + [label for _, label in METHODS],
                             cellLoc="left", colWidths=[0.07] + [0.186] * 5,
                             bbox=[0, 0, 1, 1])
            table.auto_set_font_size(False)
            table.set_fontsize(11)
            for (row, column), cell in table.get_celld().items():
                cell.set_edgecolor("#d4dee5")
                cell.set_linewidth(0.8)
                if row == 0 or column == 0:
                    cell.set_facecolor("#17354a")
                    cell.set_text_props(color="white", weight="bold", ha="center")
                else:
                    text = cell.get_text().get_text()
                    cell.set_facecolor("#fff1dc" if "FAILED" in text else "#f1f5f8")
                    cell.get_text().set_fontfamily("DejaVu Sans Mono")
                    cell.get_text().set_linespacing(1.6)
                cell.set_height(0.06 if row == 0 else 0.188)
            ax.set_position([0.055, 0.14, 0.89, 0.72])
            explanation = ("Strategy return (%) minus SPY return (%). Positive = outperformance; "
                           "negative = underperformance." if relative_to_spy
                           else "Values are saved test returns (%), not annualized.")
            fig.text(0.055, 0.105, explanation,
                     fontsize=10, color="#43596a")
            fig.text(0.055, 0.078,
                     "Variant 1 = no numeric suffix; variant 2 = numeric suffix. SPY is the reference benchmark.",
                     fontsize=10, color="#43596a")
            fig.text(0.055, 0.051,
                     "Seed order: 11, 22, 33, 42, 55. FAILED = missing final test result, not zero. "
                     "Completed: {}/125.".format(counts.get("Completed", 0)),
                     fontsize=10, color="#43596a")
            fig.text(0.945, 0.025, "{} / {}".format(page, len(STRATEGIES)),
                     ha="right", fontsize=9, color="#43596a")
            pdf.savefig(fig)
            if page == 1:
                fig.savefig(path.with_name("preview_emperor_1.png"), dpi=140)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--relative-to-spy", action="store_true",
                        help="Show strategy return minus SPY return in percentage points.")
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output or root / ("spy_relative_performance_tables" if args.relative_to_spy
                                   else "performance_tables")
    basename = "masterpeng_relative_to_spy" if args.relative_to_spy else "masterpeng_performance"
    records, failures, counts = collect(root)
    lookup = {(r["year"], r["method"], r["seed"], r["strategy"], r["variant"]): r
              for r in records}
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / (basename + ".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    write_xlsx(output / (basename + ".xlsx"), records, lookup, failures, counts,
               relative_to_spy=args.relative_to_spy, root=root)
    if not args.skip_pdf:
        write_pdf(output / (basename + ".pdf"), lookup, counts,
                  relative_to_spy=args.relative_to_spy)
    print(json.dumps({"output": str(output), "runs": counts, "tables": len(STRATEGIES),
                      "cells_per_table": 25, "seed_results_per_cell": 5,
                      "metric": "excess_return_pp" if args.relative_to_spy else "return_pct",
                      "saved_returns": sum(r["return_pct"] is not None for r in records),
                      "missing_returns": sum(r["return_pct"] is None for r in records)}, indent=2))


if __name__ == "__main__":
    main()
