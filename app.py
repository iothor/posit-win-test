import subprocess
import os
from shiny import App, ui, render, reactive

app_ui = ui.page_fluid(
    ui.h2("Run .exe on Linux Test"),
    ui.p("Click the button to attempt running hello.exe. On Linux, this will show whether the binary executes natively."),
    ui.input_action_button("run_btn", "Run hello.exe", class_="btn-primary"),
    ui.br(),
    ui.br(),
    ui.h4("Output:"),
    ui.output_text_verbatim("result"),
)

def server(input, output, session):
    run_result = reactive.value("(not run yet)")

    @reactive.effect
    @reactive.event(input.run_btn)
    def _():
        exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hello.exe")

        if not os.path.exists(exe_path):
            run_result.set(f"ERROR: hello.exe not found at:\n{exe_path}")
            return

        try:
            proc = subprocess.run(
                [exe_path],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = [
                f"Exit code : {proc.returncode}",
                f"Stdout    : {proc.stdout.strip() or '(empty)'}",
                f"Stderr    : {proc.stderr.strip() or '(empty)'}",
            ]
            run_result.set("\n".join(lines))
        except PermissionError as e:
            run_result.set(f"ERROR – Permission denied:\n{e}")
        except subprocess.TimeoutExpired:
            run_result.set("ERROR – Execution timed out after 10 s")
        except OSError as e:
            run_result.set(
                f"ERROR – OS error (likely not a valid ELF binary on Linux):\n{e}"
            )
        except Exception as e:
            run_result.set(f"ERROR – {type(e).__name__}: {e}")

    @output
    @render.text
    def result():
        return run_result()

app = App(app_ui, server)
