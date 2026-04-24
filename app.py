import subprocess
import os
import stat
import platform
from shiny import App, ui, render, reactive

app_ui = ui.page_fluid(
    ui.h2("Run .exe on Linux Test"),
    ui.p("Click the buttons below to install Wine, set permissions, and run hello.exe."),
    ui.div(
        ui.input_action_button("install_wine_btn", "Install Wine", class_="btn-warning"),
        ui.input_action_button("chmod_btn", "Set Executable Permission", class_="btn-secondary"),
        ui.input_action_button("run_btn", "Run hello.exe", class_="btn-primary"),
        style="display: flex; gap: 10px; flex-wrap: wrap;",
    ),
    ui.br(),
    ui.h4("Output:"),
    ui.output_text_verbatim("result"),
)

def server(input, output, session):
    run_result = reactive.value("(not run yet)")

    exe_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hello.exe")

    # ── Install Wine ─────────────────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.install_wine_btn)
    def _install_wine():
        if platform.system() != "Linux":
            run_result.set("Wine installation is only supported on Linux.")
            return

        # Check if wine is already installed
        check = subprocess.run(["which", "wine"], capture_output=True, text=True)
        if check.returncode == 0:
            run_result.set(f"Wine is already installed at: {check.stdout.strip()}")
            return

        run_result.set("Installing Wine… (this may take a minute)")

        # Try without sudo first (containers often run as root),
        # then fall back to sudo variants.
        for cmd in (
            ["apt-get", "install", "-y", "wine"],
            ["dnf",     "install", "-y", "wine"],
            ["sudo", "apt-get", "install", "-y", "wine"],
            ["sudo", "dnf",     "install", "-y", "wine"],
        ):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode == 0:
                run_result.set(
                    f"Wine installed successfully via '{cmd[1]}'.\n\n"
                    f"Stdout:\n{proc.stdout.strip()}"
                )
                return

        run_result.set(
            f"Wine installation failed.\n\n"
            f"Stdout:\n{proc.stdout.strip()}\n\nStderr:\n{proc.stderr.strip()}"
        )

    # ── Set executable permission ─────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.chmod_btn)
    def _chmod():
        if not os.path.exists(exe_path):
            run_result.set(f"ERROR: hello.exe not found at:\n{exe_path}")
            return

        try:
            current = os.stat(exe_path).st_mode
            os.chmod(exe_path, current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            new_mode = oct(os.stat(exe_path).st_mode)
            run_result.set(f"Permissions set successfully.\nNew mode: {new_mode}\nPath: {exe_path}")
        except Exception as e:
            run_result.set(f"ERROR setting permissions: {e}")

    # ── Run hello.exe ─────────────────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.run_btn)
    def _run_exe():
        if not os.path.exists(exe_path):
            run_result.set(f"ERROR: hello.exe not found at:\n{exe_path}")
            return

        # On Linux, try to run via wine if available; fall back to direct exec
        if platform.system() == "Linux":
            wine_check = subprocess.run(["which", "wine"], capture_output=True, text=True)
            if wine_check.returncode == 0:
                cmd = ["wine", exe_path]
            else:
                cmd = [exe_path]
        else:
            cmd = [exe_path]

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = [
                f"Command   : {' '.join(cmd)}",
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
