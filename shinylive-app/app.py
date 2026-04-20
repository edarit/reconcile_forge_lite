from __future__ import annotations

import csv
import io
import re
from typing import Any

from shiny import App, reactive, render, ui

app_ui = ui.page_fluid(
    ui.tags.style("""
    .app-note { color: #555; margin-top: -0.4rem; }
    .small-muted { color: #666; font-size: 0.92rem; }
    .shiny-output-error { color: #b00020; }
    """),

    ui.h2("Excel Reconciliation Lite — Shinylive"),
    ui.p(
        "Browser-only Lite version for GitHub Pages. CSV only, no pandas, no openpyxl, faster and more stable for demo use.",
        class_="app-note",
    ),

    ui.layout_sidebar(
        ui.sidebar(
            ui.input_file("file1", "Upload File 1 (CSV)", accept=[".csv"], multiple=False),
            ui.input_file("file2", "Upload File 2 (CSV)", accept=[".csv"], multiple=False),

            ui.hr(),
            ui.output_ui("column_controls"),

            ui.input_action_button("run", "Run reconciliation", class_="btn-primary"),

            ui.hr(),
            ui.download_button("download_csv", "Download Result CSV"),

            ui.hr(),
            ui.h5("Lite limits"),
            ui.tags.ul(
                ui.tags.li("CSV only"),
                ui.tags.li("Basic row matching"),
                ui.tags.li("No Excel formatting"),
                ui.tags.li("No grouped asset logic"),
                ui.tags.li("No audit wording automation"),
            ),
            ui.p(
                "Pro version can handle Excel, formatting, grouping logic, and auditor-friendly explanations.",
                class_="small-muted",
            ),
            width=360,
        ),

        ui.h4("Summary"),
        ui.output_ui("summary_ui"),
        ui.hr(),
        ui.h4("Preview"),
        ui.output_table("preview"),
    )
)


def get_fileinfo(file_input_value):
    if not file_input_value:
        return None
    if isinstance(file_input_value, list):
        return file_input_value[0]
    return file_input_value


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"\s+", " ", text).strip().upper()
    return text


def parse_number(value: Any):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def read_csv_rows(fileinfo) -> list[dict[str, str]]:
    path = fileinfo["datapath"] if isinstance(fileinfo, dict) else fileinfo.datapath
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            clean_row = {}
            for k, v in row.items():
                key = "" if k is None else str(k).strip()
                clean_row[key] = "" if v is None else str(v)
            rows.append(clean_row)
        return rows


def get_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    return list(rows[0].keys())


def index_by_key(rows: list[dict[str, str]], key_col: str) -> dict[str, dict[str, str]]:
    indexed = {}
    for row in rows:
        raw = row.get(key_col, "")
        norm = normalize_value(raw)
        if norm == "":
            continue
        if norm not in indexed:
            indexed[norm] = row
    return indexed


def compare_field(left_row, right_row, left_col: str, right_col: str, label: str) -> str:
    if not left_col or not right_col:
        return ""

    left_val = left_row.get(left_col, "")
    right_val = right_row.get(right_col, "")

    if label == "value":
        ln = parse_number(left_val)
        rn = parse_number(right_val)
        if ln is None and rn is None:
            return ""
        if ln != rn:
            return "VALUE_MISMATCH"
        return ""

    lv = normalize_value(left_val)
    rv = normalize_value(right_val)

    if lv == "" and rv == "":
        return ""

    if lv != rv:
        return f"{label.upper()}_MISMATCH"

    return ""


def build_result(
    rows1: list[dict[str, str]],
    rows2: list[dict[str, str]],
    key1: str,
    key2: str,
    desc1: str = "",
    desc2: str = "",
    code1: str = "",
    code2: str = "",
    val1: str = "",
    val2: str = "",
) -> list[dict[str, Any]]:
    idx1 = index_by_key(rows1, key1)
    idx2 = index_by_key(rows2, key2)

    all_keys = sorted(set(idx1.keys()) | set(idx2.keys()))
    out = []

    for match_key in all_keys:
        left = idx1.get(match_key)
        right = idx2.get(match_key)

        result_row = {
            "status": "MATCH",
            "issue_details": "-",
            "match_key": match_key,
            "file1_key": "" if left is None else left.get(key1, ""),
            "file2_key": "" if right is None else right.get(key2, ""),
            "file1_description": "" if left is None or not desc1 else left.get(desc1, ""),
            "file2_description": "" if right is None or not desc2 else right.get(desc2, ""),
            "file1_code": "" if left is None or not code1 else left.get(code1, ""),
            "file2_code": "" if right is None or not code2 else right.get(code2, ""),
            "file1_value": "" if left is None or not val1 else left.get(val1, ""),
            "file2_value": "" if right is None or not val2 else right.get(val2, ""),
        }

        if left is not None and right is None:
            result_row["status"] = "MISSING_IN_FILE_2"
            result_row["issue_details"] = "Missing in File 2"
        elif left is None and right is not None:
            result_row["status"] = "MISSING_IN_FILE_1"
            result_row["issue_details"] = "Missing in File 1"
        else:
            issues = []

            desc_issue = compare_field(left, right, desc1, desc2, "description")
            code_issue = compare_field(left, right, code1, code2, "code")
            val_issue = compare_field(left, right, val1, val2, "value")

            for item in [desc_issue, code_issue, val_issue]:
                if item:
                    issues.append(item)

            if issues:
                result_row["status"] = "FIELD_MISMATCH"
                result_row["issue_details"] = "; ".join(issues)

        out.append(result_row)

    return out


def rows_to_csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "status,issue_details,match_key,file1_key,file2_key\n"

    output = io.StringIO()
    fieldnames = list(rows[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def server(input, output, session):
    @reactive.calc
    def file1_info():
        return get_fileinfo(input.file1())

    @reactive.calc
    def file2_info():
        return get_fileinfo(input.file2())

    @reactive.calc
    def rows1():
        if file1_info() is None:
            raise ValueError("Upload File 1 first.")
        return read_csv_rows(file1_info())

    @reactive.calc
    def rows2():
        if file2_info() is None:
            raise ValueError("Upload File 2 first.")
        return read_csv_rows(file2_info())

    @output
    @render.ui
    def column_controls():
        if file1_info() is None or file2_info() is None:
            return ui.p("Upload both CSV files to map keys and optional comparison columns.", class_="small-muted")

        try:
            cols1 = get_columns(rows1())
            cols2 = get_columns(rows2())
        except Exception as e:
            return ui.div(ui.strong("Could not read the CSV files: "), str(e))

        if not cols1 or not cols2:
            return ui.p("One of the files appears empty or has no header row.", class_="small-muted")

        blank = {"": "(skip)"}
        choices1 = {c: c for c in cols1}
        choices2 = {c: c for c in cols2}

        return ui.TagList(
            ui.h5("Column mapping"),
            ui.layout_columns(
                ui.TagList(
                    ui.input_select("key1", "File 1 match key", choices=choices1, selected=cols1[0]),
                    ui.input_select("desc1", "File 1 description", choices={**blank, **choices1}, selected=""),
                    ui.input_select("code1", "File 1 code", choices={**blank, **choices1}, selected=""),
                    ui.input_select("val1", "File 1 value", choices={**blank, **choices1}, selected=""),
                ),
                ui.TagList(
                    ui.input_select("key2", "File 2 match key", choices=choices2, selected=cols2[0]),
                    ui.input_select("desc2", "File 2 description", choices={**blank, **choices2}, selected=""),
                    ui.input_select("code2", "File 2 code", choices={**blank, **choices2}, selected=""),
                    ui.input_select("val2", "File 2 value", choices={**blank, **choices2}, selected=""),
                ),
                col_widths=[6, 6],
            ),
        )

    @reactive.calc
    @reactive.event(input.run)
    def result_rows():
        if file1_info() is None or file2_info() is None:
            raise ValueError("Upload both files before running reconciliation.")

        return build_result(
            rows1(),
            rows2(),
            input.key1(),
            input.key2(),
            input.desc1() or "",
            input.desc2() or "",
            input.code1() or "",
            input.code2() or "",
            input.val1() or "",
            input.val2() or "",
        )

    @output
    @render.ui
    def summary_ui():
        try:
            result = result_rows()
        except Exception:
            return ui.p("Run reconciliation to see the result summary.", class_="small-muted")

        total = len(result)
        counts = {
            "MATCH": 0,
            "FIELD_MISMATCH": 0,
            "MISSING_IN_FILE_2": 0,
            "MISSING_IN_FILE_1": 0,
        }

        for row in result:
            status = row.get("status", "")
            if status in counts:
                counts[status] += 1

        return ui.TagList(
            ui.p(f"Total rows in result: {total}"),
            ui.tags.ul(
                ui.tags.li(f"MATCH: {counts['MATCH']}"),
                ui.tags.li(f"FIELD_MISMATCH: {counts['FIELD_MISMATCH']}"),
                ui.tags.li(f"MISSING_IN_FILE_2: {counts['MISSING_IN_FILE_2']}"),
                ui.tags.li(f"MISSING_IN_FILE_1: {counts['MISSING_IN_FILE_1']}"),
            ),
        )

    # @output
    # @render.table
    # def preview():
    #     try:
    #         return result_rows()
    #     except Exception:
    #         return [{"info": "No result yet. Upload two CSV files, map columns, then click Run reconciliation."}]

    @output
    @render.ui
    def preview():
        try:
            data = result_rows()
            if not data:
                return ui.p("No results.")
                
            # Manually build a simple HTML table
            header = [ui.tags.th(k) for k in data[0].keys()]
            rows = []
            for row in data[:10]: # Limit to first 10 for preview
                rows.append(ui.tags.tr([ui.tags.td(str(v)) for v in row.values()]))
                
            return ui.tags.table(
                ui.tags.thead(ui.tags.tr(header)),
                ui.tags.tbody(rows),
                class_="table shiny-table w-auto"
            )
        except Exception:
            return ui.p("Upload files and click Run.")
    
    @output
    @render.download(filename="reconciliation_lite.csv")
    def download_csv():
        try:
            result = result_rows()
        except Exception:
            result = []
        yield rows_to_csv_text(result)


app = App(app_ui, server)
