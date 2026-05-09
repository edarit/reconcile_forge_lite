from shiny import App, ui, render, reactive
import pandas as pd
from io import BytesIO

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_file("file1", "Upload File 1", accept=[".xlsx", ".xls"]),
        ui.output_ui("sheet1_ui"),
        ui.output_ui("cols1_ui"),
        ui.hr(),
        ui.input_file("file2", "Upload File 2", accept=[".xlsx", ".xls"]),
        ui.output_ui("sheet2_ui"),
        ui.output_ui("cols2_ui"),
        ui.hr(),
        ui.input_action_button("run", "Run Reconciliation", class_="btn-primary"),
        width=320,
    ),
    ui.h2("Reconcile Forge Lite"),
    ui.p("Upload 2 Excel files, select sheet and columns, then compare."),
    ui.h4("Mismatch Results"),
    ui.output_data_frame("result_table"),
    ui.hr(),
    ui.h4("Basic Reconciliation Report"),
    ui.output_text_verbatim("report"),
    ui.div(
        ui.download_button("download_xlsx", "Download Result as Excel"),
        style="margin: 12px 0;"
    ),
    ui.card(
        ui.card_header("Pro Version"),
        ui.p("Unlock audit-ready explanations, grouped asset logic, and fuller reconciliation reporting."),
        ui.p("CTA: Upgrade to Pro Report"),
    ),
    title="Shinylive Excel Reconciliation App",
)


def read_excel_sheets(fileinfo):
    if not fileinfo:
        return {}
    try:
        path = fileinfo[0]["datapath"]
        return pd.read_excel(path, sheet_name=None)
    except Exception:
        return {}


def normalize_series(s):
    return s.astype(str).fillna("").str.strip()


def build_result(df1, df2, id1, desc1, id2, desc2):
    a = df1[[id1, desc1]].copy()
    b = df2[[id2, desc2]].copy()

    a.columns = ["id_file1", "desc_file1"]
    b.columns = ["id_file2", "desc_file2"]

    a["match_id"] = normalize_series(a["id_file1"]).str.upper()
    b["match_id"] = normalize_series(b["id_file2"]).str.upper()

    merged = a.merge(b, on="match_id", how="outer", indicator=True)

    def issue(row):
        if row["_merge"] == "left_only":
            return "Missing in File 2"
        if row["_merge"] == "right_only":
            return "Missing in File 1"
        d1 = str(row.get("desc_file1", "")).strip()
        d2 = str(row.get("desc_file2", "")).strip()
        if d1 != d2:
            return "Description mismatch"
        return ""

    merged["issue"] = merged.apply(issue, axis=1)

    out = merged.loc[merged["issue"] != "", [
        "id_file1", "desc_file1", "id_file2", "desc_file2", "issue"
    ]].copy()

    return out.reset_index(drop=True)


def df_to_excel_bytes(df):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="reconciliation")
    buf.seek(0)
    return buf.read()


def server(input, output, session):
    sheets1 = reactive.Value({})
    sheets2 = reactive.Value({})
    result_val = reactive.Value(pd.DataFrame())

    @reactive.effect
    def _load1():
        sheets1.set(read_excel_sheets(input.file1()))

    @reactive.effect
    def _load2():
        sheets2.set(read_excel_sheets(input.file2()))

    @output
    @render.ui
    def sheet1_ui():
        names = list(sheets1().keys())
        if not names:
            return ui.div()
        return ui.input_select("sheet1", "Sheet (File 1)", choices=names, selected=names[0])

    @output
    @render.ui
    def sheet2_ui():
        names = list(sheets2().keys())
        if not names:
            return ui.div()
        return ui.input_select("sheet2", "Sheet (File 2)", choices=names, selected=names[0])

    @output
    @render.ui
    def cols1_ui():
        sname = input.sheet1()
        if not sname or sname not in sheets1():
            return ui.div()
        cols = [str(c) for c in sheets1()[sname].columns]
        if not cols:
            return ui.div()
        return ui.TagList(
            ui.input_select("id1", "ID column (File 1)", choices=cols, selected=cols[0]),
            ui.input_select("desc1", "Description column (File 1)", choices=cols, selected=cols[min(1, len(cols)-1)]),
        )

    @output
    @render.ui
    def cols2_ui():
        sname = input.sheet2()
        if not sname or sname not in sheets2():
            return ui.div()
        cols = [str(c) for c in sheets2()[sname].columns]
        if not cols:
            return ui.div()
        return ui.TagList(
            ui.input_select("id2", "ID column (File 2)", choices=cols, selected=cols[0]),
            ui.input_select("desc2", "Description column (File 2)", choices=cols, selected=cols[min(1, len(cols)-1)]),
        )

    @reactive.effect
    @reactive.event(input.run)
    def _run():
        try:
            df1 = sheets1()[input.sheet1()]
            df2 = sheets2()[input.sheet2()]
            result = build_result(
                df1, df2,
                input.id1(), input.desc1(),
                input.id2(), input.desc2()
            )
            result_val.set(result)
        except Exception:
            result_val.set(pd.DataFrame())

    @output
    @render.data_frame
    def result_table():
        return render.DataGrid(result_val(), width="100%", height="420px")

    @output
    @render.text
    def report():
        df = result_val()
        if df.empty:
            return "No mismatches found."
        total = len(df)
        counts = df["issue"].value_counts().to_dict()
        lines = [f"Total mismatches: {total}"]
        for k, v in counts.items():
            lines.append(f"{k}: {v}")
        lines.append("")
        lines.append("Lite version completed basic ID and description reconciliation.")
        lines.append("Upgrade to Pro for explanation notes and fuller audit wording.")
        return "\n".join(lines)

    @output
    @render.download(filename="reconciliation_result.xlsx")
    def download_xlsx():
        data = df_to_excel_bytes(result_val())
        yield data


app = App(app_ui, server)
