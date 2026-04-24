import subprocess
import os
import stat
import platform
import shutil
from shiny import App, ui, render, reactive

APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Portable wine is extracted here (no root needed)
WINE_PORTABLE_DIR = os.path.join(APP_DIR, "wine-portable")
WINE_PORTABLE_TARBALL = os.path.join(APP_DIR, "wine-portable.tar.xz")



def _find_wine() -> str | None:
    """Return path to a usable wine binary, or None."""
    # 1. portable wine bundled / extracted in the app directory
    for candidate in (
        os.path.join(WINE_PORTABLE_DIR, "bin", "wine"),
        os.path.join(WINE_PORTABLE_DIR, "wine-10.0-amd64", "bin", "wine"),
    ):
        if os.path.isfile(candidate):
            return candidate
    # 2. system wine
    system_wine = shutil.which("wine")
    if system_wine:
        return system_wine
    return None

app_ui = ui.page_fluid(
    ui.h2("Run .exe on Linux Test"),
    ui.p(
        "Click the buttons below to install Wine, set permissions, and run hello.exe."
    ),
    ui.div(
        ui.input_action_button(
            "install_wine_btn", "Install Wine", class_="btn-warning"
        ),
        ui.input_action_button(
            "chmod_btn", "Set Executable Permission", class_="btn-secondary"
        ),
        ui.input_action_button("run_btn", "Run hello.exe", class_="btn-primary"),
        style="display: flex; gap: 10px; flex-wrap: wrap;",
    ),
    ui.br(),
    ui.h4("Output:"),
    ui.output_text_verbatim("result"),
)


def server(input, output, session):
    run_result = reactive.value("(not run yet)")

    exe_path = os.path.join(APP_DIR, "hello.exe")

    # ── Install Wine ─────────────────────────────────────────────────────────
    @reactive.effect
    @reactive.event(input.install_wine_btn)
    def _install_wine():
        if platform.system() != "Linux":
            run_result.set("Wine installation is only supported on Linux.")
            return

        existing = _find_wine()
        if existing:
            run_result.set(f"Wine is already available at: {existing}")
            return

        run_result.set("Installing Wine… (this may take a minute)")

        log = []

        def _try(cmd, label, timeout=300):
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if proc.returncode == 0:
                run_result.set(
                    f"Wine installed successfully via {label}.\n\nStdout:\n{proc.stdout.strip()}"
                )
                return True
            log.append(
                f"[{label}] exit={proc.returncode}\n"
                f"  stderr: {proc.stderr.strip()[:300]}"
            )
            return False

        # 1. ── Portable tarball already in the repo ───────────────────────────
        if os.path.isfile(WINE_PORTABLE_TARBALL):
            try:
                run_result.set(f"Extracting bundled {WINE_PORTABLE_TARBALL} …")
                with tarfile.open(WINE_PORTABLE_TARBALL, "r:xz") as tf:
                    tf.extractall(WINE_PORTABLE_DIR)
                wine_bin = _find_wine()
                if wine_bin:
                    os.chmod(wine_bin, os.stat(wine_bin).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                    run_result.set(f"Portable Wine extracted and ready at: {wine_bin}")
                    return
                log.append("[portable-tarball] extracted but wine binary not found inside")
            except Exception as e:
                log.append(f"[portable-tarball] extraction failed: {e}")

        # 2. ── System package managers ────────────────────────────────────────
        for cmd, label in [
            (["apt-get", "install", "-y", "wine"], "apt-get"),
            (["dnf", "install", "-y", "wine"], "dnf"),
            (["sudo", "apt-get", "install", "-y", "wine"], "sudo apt-get"),
            (["sudo", "dnf", "install", "-y", "wine"], "sudo dnf"),
        ]:
            pkg_mgr = cmd[1] if cmd[0] == "sudo" else cmd[0]
            if shutil.which(cmd[0]) and shutil.which(pkg_mgr):
                if _try(cmd, label):
                    return

        run_result.set(
            "Wine installation failed. All methods tried:\n\n"
            + "\n\n".join(log)
            + "\n\nTip: download wine-portable.tar.xz from\n"
            + WINE_PORTABLE_URL
            + "\nand place it next to app.py in the repository."
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
            run_result.set(
                f"Permissions set successfully.\nNew mode: {new_mode}\nPath: {exe_path}"
            )
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
            wine_bin = _find_wine()
            if wine_bin:
                cmd = [wine_bin, exe_path]
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
