# 文件名：ui.py
"""用于课堂演示的本地 Tkinter 图形界面。

界面复用 main.py 的核心流程，不复制表格提取或合并逻辑，因此命令行和
图形界面的输出行为保持一致。Tkinter 属于 Python 标准库，不需要新增依赖。
"""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional, Tuple

from main import run


PROJECT_ROOT = Path(__file__).resolve().parent


def configure_bundled_java() -> Optional[Path]:
    """优先使用项目内的 Temurin JRE，方便课堂电脑没有全局 Java 时演示。"""

    bundled_java = PROJECT_ROOT / ".runtime" / "temurin17-jre"
    java_executable = bundled_java / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not java_executable.exists():
        return None

    os.environ["JAVA_HOME"] = str(bundled_java)
    current_path = os.environ.get("PATH", "")
    java_bin = str(bundled_java / "bin")
    if java_bin not in current_path.split(os.pathsep):
        os.environ["PATH"] = java_bin + os.pathsep + current_path
    return bundled_java


def default_pdf() -> Path:
    """课堂演示优先使用会产生冲突报告的陌生布局样例。"""

    candidates = [
        PROJECT_ROOT / "test" / "data" / "category3_unfamiliar_layout" / "sample_01.pdf",
        PROJECT_ROOT / "test" / "data" / "category1_standard" / "sample_01.pdf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return PROJECT_ROOT / "input.pdf"


class ReconstructionUI:
    """简洁的课堂演示窗口。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Auditable PDF Table Reconstruction")
        self.root.geometry("980x700")
        self.root.minsize(820, 580)

        self.input_var = tk.StringVar(value=str(default_pdf()))
        self.output_var = tk.StringVar(value=str(PROJECT_ROOT / "demo_ui_output"))
        self.status_var = tk.StringVar(value="Ready. Choose a PDF and run a mode.")
        self.events: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.running = False

        self._build_widgets()
        self._append_log("Auditable Cross-Page PDF Table Reconstruction")
        self._append_log("Improved mode checks headers, column counts and units.")
        self._append_log("Baseline mode is available for comparison.")
        bundled_java = configure_bundled_java()
        if bundled_java:
            self._append_log(f"Using bundled Java runtime: {bundled_java}")
        else:
            self._append_log("Using system Java. Java 8+ is required by tabula-py.")
        self._refresh_outputs()
        self.root.after(150, self._poll_events)

    def _build_widgets(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(3, weight=1)

        title = ttk.Label(
            self.root,
            text="Auditable Cross-Page PDF Table Reconstruction",
            font=("Segoe UI", 17, "bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")
        subtitle = ttk.Label(
            self.root,
            text="Native-text PDF only | Outputs: reconstructed CSV + audit trail + conflict report",
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 14), sticky="w")

        paths = ttk.LabelFrame(self.root, text="1. Input and output")
        paths.grid(row=2, column=0, padx=20, pady=4, sticky="ew")
        paths.columnconfigure(1, weight=1)

        ttk.Label(paths, text="Input PDF:").grid(row=0, column=0, padx=10, pady=9, sticky="w")
        ttk.Entry(paths, textvariable=self.input_var).grid(row=0, column=1, padx=6, pady=9, sticky="ew")
        ttk.Button(paths, text="Browse PDF", command=self._choose_pdf).grid(row=0, column=2, padx=10, pady=9)

        ttk.Label(paths, text="Output folder:").grid(row=1, column=0, padx=10, pady=(0, 9), sticky="w")
        ttk.Entry(paths, textvariable=self.output_var).grid(row=1, column=1, padx=6, pady=(0, 9), sticky="ew")
        ttk.Button(paths, text="Choose folder", command=self._choose_output).grid(row=1, column=2, padx=10, pady=(0, 9))

        content = ttk.PanedWindow(self.root, orient="horizontal")
        content.grid(row=3, column=0, padx=20, pady=12, sticky="nsew")

        actions = ttk.LabelFrame(content, text="2. Run prototype")
        actions.columnconfigure(0, weight=1)
        ttk.Label(
            actions,
            text="Improved mode is recommended for the demonstration.\nBaseline mode is the comparison group.",
            justify="left",
        ).grid(row=0, column=0, padx=14, pady=(18, 14), sticky="w")
        self.improved_button = ttk.Button(
            actions,
            text="Run improved mode",
            command=lambda: self._start_run(baseline=False),
        )
        self.improved_button.grid(row=1, column=0, padx=14, pady=7, sticky="ew")
        self.baseline_button = ttk.Button(
            actions,
            text="Run baseline mode",
            command=lambda: self._start_run(baseline=True),
        )
        self.baseline_button.grid(row=2, column=0, padx=14, pady=7, sticky="ew")
        ttk.Button(actions, text="Open output folder", command=self._open_output_folder).grid(
            row=3, column=0, padx=14, pady=(20, 7), sticky="ew"
        )
        ttk.Button(actions, text="Clear log", command=self._clear_log).grid(
            row=4, column=0, padx=14, pady=7, sticky="ew"
        )
        ttk.Label(
            actions,
            text="Tip: use category3_unfamiliar_layout/sample_01.pdf\nto show a conflict report.",
            foreground="#555555",
            justify="left",
        ).grid(row=5, column=0, padx=14, pady=(22, 12), sticky="w")
        content.add(actions, weight=0)

        output_frame = ttk.LabelFrame(content, text="3. Output files")
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)
        self.output_list = tk.Listbox(output_frame, height=10, activestyle="dotbox")
        self.output_list.grid(row=0, column=0, padx=(10, 0), pady=10, sticky="nsew")
        output_scroll = ttk.Scrollbar(output_frame, orient="vertical", command=self.output_list.yview)
        output_scroll.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ns")
        self.output_list.configure(yscrollcommand=output_scroll.set)
        self.output_list.bind("<Double-Button-1>", lambda _event: self._open_selected_output())
        ttk.Label(output_frame, text="Double-click a CSV to open it.").grid(
            row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w"
        )
        content.add(output_frame, weight=1)

        log_frame = ttk.LabelFrame(self.root, text="Run log")
        log_frame.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.root.rowconfigure(4, weight=1)
        self.log_text = tk.Text(log_frame, height=9, wrap="word", state="disabled", background="#f7f7f7")
        self.log_text.grid(row=0, column=0, padx=(8, 0), pady=8, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")

    def _choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose a native-text PDF",
            initialdir=str(PROJECT_ROOT),
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if selected:
            self.input_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="Choose output folder", initialdir=str(PROJECT_ROOT))
        if selected:
            self.output_var.set(selected)
            self._refresh_outputs()

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self.improved_button.configure(state=state)
        self.baseline_button.configure(state=state)

    def _start_run(self, baseline: bool) -> None:
        if self.running:
            return
        pdf_path = Path(self.input_var.get().strip()).expanduser()
        output_path = Path(self.output_var.get().strip()).expanduser()
        if not pdf_path.exists() or not pdf_path.is_file():
            messagebox.showerror("Input error", f"PDF file does not exist:\n{pdf_path}")
            return
        if pdf_path.suffix.lower() != ".pdf":
            messagebox.showerror("Input error", "Please choose a PDF file.")
            return
        if not str(output_path):
            messagebox.showerror("Output error", "Please choose an output folder.")
            return

        self.running = True
        self._set_buttons(False)
        mode = "baseline" if baseline else "improved"
        self.status_var.set(f"Running {mode} mode...")
        self._append_log(f"\n--- Running {mode} mode ---")
        self._append_log(f"Input: {pdf_path}")
        self._append_log(f"Output: {output_path}")
        worker = threading.Thread(
            target=self._run_in_background,
            args=(pdf_path, output_path, baseline),
            daemon=True,
        )
        worker.start()

    def _run_in_background(self, pdf_path: Path, output_path: Path, baseline: bool) -> None:
        captured = io.StringIO()
        try:
            with redirect_stdout(captured), redirect_stderr(captured):
                return_code = run(pdf_path, output_path, baseline=baseline)
            self.events.put(("done", (return_code, captured.getvalue(), output_path)))
        except Exception:
            self.events.put(("error", traceback.format_exc()))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "done":
                    return_code, output, output_path = payload  # type: ignore[misc]
                    if output:
                        self._append_log(output)
                    self.running = False
                    self._set_buttons(True)
                    if return_code == 0:
                        self.status_var.set("Completed successfully. Open the output files for the demonstration.")
                        self._refresh_outputs()
                    else:
                        self.status_var.set(f"Finished with return code {return_code}.")
                        self._refresh_outputs()
                elif kind == "error":
                    self.running = False
                    self._set_buttons(True)
                    self.status_var.set("Run failed. See the log for details.")
                    self._append_log(str(payload))
                    messagebox.showerror("Run failed", "The prototype raised an error. See the run log.")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_events)

    def _refresh_outputs(self) -> None:
        self.output_list.delete(0, "end")
        output_path = Path(self.output_var.get().strip()).expanduser()
        if not output_path.exists():
            self.output_list.insert("end", "(No output folder yet)")
            return
        files = sorted(output_path.glob("*.csv"))
        if not files:
            self.output_list.insert("end", "(No CSV outputs yet)")
            return
        for file_path in files:
            self.output_list.insert("end", str(file_path))

    def _open_output_folder(self) -> None:
        output_path = Path(self.output_var.get().strip()).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)
        self._open_path(output_path)

    def _open_selected_output(self) -> None:
        selection = self.output_list.curselection()
        if not selection:
            return
        selected = Path(self.output_list.get(selection[0]))
        if selected.exists():
            self._open_path(selected)

    @staticmethod
    def _open_path(path: Path) -> None:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])


def main() -> None:
    root = tk.Tk()
    ReconstructionUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
