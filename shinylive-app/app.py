from __future__ import annotations

import pandas as pd
from shiny import reactive, render, ui
from shiny.express import input

ui.page_opts(title="Excel Reconciliation Lite — Shinylive CSV", fillable=True)

ui.tags.style(
    """
    .app-note { color: #555; margin-top: -0.4rem; }
    .small-muted { color: #666; font-size: 0.92rem; }
    .shiny-output-error { color: #b00020; }
    """
)

ui.h2("Excel Reconciliation Engine Lite — Shinylive")
ui.p(
    "CSV-only browser version for GitHub Pages. Use this for the most stable Shinylive deployment.",
    class_="app-note",
)

with ui.sidebar(width=360):
    ui.input_file("file1", "Upload File 1 (CSV)", accept=[".csv"], multiple=False)
    ui.input_file("file2", "Upload File 2 (CSV)", accept=[".csv"], multiple=False)
    ui.output_ui("column_controls")
    ui.input_action_button("run", "Run reconciliation", class_="btn-primary")
    ui.hr()
    ui.download_button("download_csv", "Download CSV")


@render.express
def summary_block():
    ui.h4("Summary")
    ui.output_ui("summary_ui")


ui.output_data_frame("preview")


def normalize_series(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype(str)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )


def get_fileinfo(file_input_value):
    if not file_input_value:
        return None
    if isinstance(file_input_value, list):
        return file_input_value[0]
    return file_input_value


def read_uploaded_csv(fileinfo) -> pd.DataFrame:
    path = fileinfo["datapath"] if isinstance(fileinfo, dict) else fileinfo.datapath
    return pd.read_csv(path)


def build_result(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    key1: str,
    key2: str,
    desc1: str = "",
    desc2: str = "",
    code1: str = "",
    code2: str = "",
    val1: str = "",
    val2: str = "",
) -> pd.DataFrame:
    left = df1.copy()
    right = df2.copy()

    left["__match_key__"] = normalize_series(left[key1])
    right["__match_key__"] = normalize_series(right[key2])

    left = left.drop_duplicates(subset=["__match_key__"], keep="first")
    right = right.drop_duplicates(subset=["__match_key__"], keep="first")

    merged = left.merge(
        right,
        on="__match_key__",
        how="outer",
        suffixes=("_f1", "_f2"),
        indicator=True,
    )

    out = pd.DataFrame(
        {
            "status": "MATCH",
            "issue_details": "-",
            "match_key": merged["__match_key__"],
            "file1_key": merged.get(f"{key1}_f1", ""),
            "file2_key": merged.get(f"{key2}_f2", ""),
        }
    )

    out.loc[merged["_merge"] == "left_only", "status"] = "MISSING_IN_FILE_2"
    out.loc[merged["_merge"] == "right_only", "status"] = "MISSING_IN_FILE_1"

    def add_pair(a: str, b: str, label: str) -> None:
        if not a or not b:
            return
        la = f"{a}_f1"
        lb = f"{b}_f2"
        if la not in merged.columns or lb not in merged.columns:
            return

        if label == "value":
            va = pd.to_numeric(merged[la], errors="coerce")
            vb = pd.to_numeric(merged[lb], errors="coerce")
            mismatch = merged["_merge"].eq("both") & ~((va.isna() & vb.isna()) | (va == vb))
        else:
            va = normalize_series(merged[la])
            vb = normalize_series(merged[lb])
            mismatch = merged["_merge"].eq("both") & ~((va == "") & (vb == "")) & (va != vb)

        out.loc[mismatch, "status"] = "FIELD_MISMATCH"
        prior = out.loc[mismatch, "issue_details"].replace("-", "")
        out.loc[mismatch, "issue_details"] = prior + f"{label.upper()}_MISMATCH; "
        out[f"file1_{label}"] = merged[la]
        out[f"file2_{label}"] = merged[lb]

    add_pair(desc1, desc2, "description")
    add_pair(code1, code2, "code")
    add_pair(val1, val2, "value")

    out["issue_details"] = out["issue_details"].fillna("").str.rstrip("; ").replace("", "-")
    return out


@reactive.calc
def file1_info():
    return get_fileinfo(input.file1())


@reactive.calc
def file2_info():
    return get_fileinfo(input.file2())


@reactive.calc
def df1():
    if file1_info() is None:
        raise ValueError("Upload File 1 first.")
    return read_uploaded_csv(file1_info())


@reactive.calc
def df2():
    if file2_info() is None:
        raise ValueError("Upload File 2 first.")
    return read_uploaded_csv(file2_info())


@render.ui
def column_controls():
    if file1_info() is None or file2_info() is None:
        return ui.p("Upload both CSV files to map keys and optional comparison columns.", class_="small-muted")

    try:
        cols1 = [str(x) for x in df1().columns.tolist()]
        cols2 = [str(x) for x in df2().columns.tolist()]
    except Exception as e:
        return ui.div(ui.strong("Could not read the files: "), str(e))

    blank = {"": "(skip)"}
    choices1 = {c: c for c in cols1}
    choices2 = {c: c for c in cols2}

    return ui.TagList(
        ui.h5("Column mapping"),
        ui.layout_columns(
            ui.TagList(
                ui.input_select("key1", "File 1 match key", choices=choices1, selected=cols1[0] if cols1 else None),
                ui.input_select("desc1", "File 1 description", choices={**blank, **choices1}, selected=""),
                ui.input_select("code1", "File 1 code", choices={**blank, **choices1}, selected=""),
                ui.input_select("val1", "File 1 value", choices={**blank, **choices1}, selected=""),
            ),
            ui.TagList(
                ui.input_select("key2", "File 2 match key", choices=choices2, selected=cols2[0] if cols2 else None),
                ui.input_select("desc2", "File 2 description", choices={**blank, **choices2}, selected=""),
                ui.input_select("code2", "File 2 code", choices={**blank, **choices2}, selected=""),
                ui.input_select("val2", "File 2 value", choices={**blank, **choices2}, selected=""),
            ),
            col_widths=[6, 6],
        ),
    )


@reactive.calc
@reactive.event(input.run)
def result_df():
    if file1_info() is None or file2_info() is None:
        raise ValueError("Upload both files before running reconciliation.")
    return build_result(
        df1(),
        df2(),
        input.key1(),
        input.key2(),
        input.desc1() or "",
        input.desc2() or "",
        input.code1() or "",
        input.code2() or "",
        input.val1() or "",
        input.val2() or "",
    )


@render.ui
def summary_ui():
    try:
        result = result_df()
    except Exception:
        return ui.p("Run reconciliation to see the result summary.", class_="small-muted")

    counts = result["status"].value_counts().to_dict()
    total = len(result)
    return ui.TagList(
        ui.p(f"Total rows in result: {total}"),
        ui.tags.ul(
            ui.tags.li(f"MATCH: {counts.get('MATCH', 0)}"),
            ui.tags.li(f"FIELD_MISMATCH: {counts.get('FIELD_MISMATCH', 0)}"),
            ui.tags.li(f"MISSING_IN_FILE_2: {counts.get('MISSING_IN_FILE_2', 0)}"),
            ui.tags.li(f"MISSING_IN_FILE_1: {counts.get('MISSING_IN_FILE_1', 0)}"),
        ),
    )


@render.data_frame
def preview():
    try:
        result = result_df()
    except Exception:
        return render.DataGrid(
            pd.DataFrame(
                {
                    "info": [
                        "No result yet. Upload CSV files, map columns, then click Run reconciliation."
                    ]
                }
            ),
            width="100%",
        )
    return render.DataGrid(result, width="100%", height="600px")


@render.download(filename="reconciliation_lite.csv")
def download_csv():
    result = result_df()
    yield result.to_csv(index=False)
