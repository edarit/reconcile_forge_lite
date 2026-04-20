from shiny import App, ui, render, reactive
import pandas as pd
from io import BytesIO

def load_file(file):
    try:
        return pd.read_excel(file["datapath"], sheet_name=None)
    except:
        return {}

def reconcile(df1, df2, id1, desc1, id2, desc2):
    df1 = df1[[id1, desc1]].rename(columns={id1: "id", desc1: "desc1"})
    df2 = df2[[id2, desc2]].rename(columns={id2: "id", desc2: "desc2"})

    merged = df1.merge(df2, on="id", how="outer", indicator=True)

    def detect(row):
        if row["_merge"] == "left_only":
            return "Missing in File 2"
        if row["_merge"] == "right_only":
            return "Missing in File 1"
        if str(row["desc1"]).strip() != str(row["desc2"]).strip():
            return "Description mismatch"
        return ""

    merged["issue"] = merged.apply(detect, axis=1)
    return merged[merged["issue"] != ""].reset_index(drop=True)

app_ui = ui.page_fluid(
    ui.h2("Excel Reconciliation Lite"),

    ui.layout_sidebar(
        ui.panel_sidebar(
            ui.input_file("file1", "Upload File 1"),
            ui.output_ui("sheet1_ui"),
            ui.output_ui("col1_ui"),

            ui.hr(),

            ui.input_file("file2", "Upload File 2"),
            ui.output_ui("sheet2_ui"),
            ui.output_ui("col2_ui"),

            ui.hr(),
            ui.input_action_button("run", "Run")
        ),

        ui.panel_main(
            ui.h4("Mismatch Results"),
            ui.output_table("result"),
            ui.hr(),
            ui.h4("Report"),
            ui.output_text("report"),
            ui.download_button("download", "Download CSV"),
            ui.hr(),
            ui.markdown("### 🔒 Pro Version\n- Auto explanations\n- Grouping detection\n- Audit-ready report\n👉 Unlock Full Report")
        )
    )
)

def server(input, output, session):

    data1 = reactive.Value({})
    data2 = reactive.Value({})

    @reactive.effect
    def _():
        if input.file1():
            data1.set(load_file(input.file1()[0]))

    @reactive.effect
    def _():
        if input.file2():
            data2.set(load_file(input.file2()[0]))

    @output
    @render.ui
    def sheet1_ui():
        sheets = list(data1().keys())
        if sheets:
            return ui.input_select("sheet1", "Sheet 1", sheets)
        return ui.div()

    @output
    @render.ui
    def sheet2_ui():
        sheets = list(data2().keys())
        if sheets:
            return ui.input_select("sheet2", "Sheet 2", sheets)
        return ui.div()

    @output
    @render.ui
    def col1_ui():
        if input.sheet1():
            df = data1()[input.sheet1()]
            cols = list(df.columns)
            return ui.TagList(
                ui.input_select("id1", "ID (File 1)", cols),
                ui.input_select("desc1", "Description (File 1)", cols)
            )
        return ui.div()

    @output
    @render.ui
    def col2_ui():
        if input.sheet2():
            df = data2()[input.sheet2()]
            cols = list(df.columns)
            return ui.TagList(
                ui.input_select("id2", "ID (File 2)", cols),
                ui.input_select("desc2", "Description (File 2)", cols)
            )
        return ui.div()

    result_df = reactive.Value(pd.DataFrame())

    @reactive.effect
    @reactive.event(input.run)
    def _():
        try:
            df1 = data1()[input.sheet1()]
            df2 = data2()[input.sheet2()]
            res = reconcile(df1, df2, input.id1(), input.desc1(), input.id2(), input.desc2())
            result_df.set(res)
        except:
            result_df.set(pd.DataFrame())

    @output
    @render.table
    def result():
        return result_df().head(100)

    @output
    @render.text
    def report():
        df = result_df()
        if df.empty:
            return "No mismatches found."
        return f"Total mismatches: {len(df)}\nBasic reconciliation completed."

    @output
    @render.download
    def download():
        def content():
            df = result_df()
            return df.to_csv(index=False).encode("utf-8")
        return dict(content=content, filename="reconciliation.csv")

app = App(app_ui, server)
