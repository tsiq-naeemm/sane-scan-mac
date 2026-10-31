#!/usr/bin/env python3
"""
scanner_gui.py — a small Tkinter frontend for SANE's `scanimage`.

Built for the Canon LiDE 110 but works with any SANE-detected scanner.
Exposes the options you care about (mode, resolution, format, output
folder) and leaves everything else at the backend defaults.

The USB address SANE reports (genesys:libusb:BBB:DDD) changes whenever the
scanner re-enumerates, so we re-resolve the device right before every scan.
"""

import datetime
import os
import re
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# When launched from Finder, PATH often lacks Homebrew's bin dir, so
# `scanimage` can't be found. Put the usual locations in front.
for p in ("/opt/homebrew/bin", "/usr/local/bin"):
    if p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")

FALLBACK_RESOLUTIONS = ["75", "100", "150", "300", "600", "1200", "2400", "4800"]
DEFAULT_RESOLUTION = "300"
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Desktop")


def find_device():
    """Return the current SANE device name for the scanner, or None."""
    try:
        out = subprocess.run(
            ["scanimage", "-f", "%d%n"],
            capture_output=True, text=True, timeout=60,
        )
        for line in out.stdout.splitlines():
            line = line.strip()
            if "genesys" in line or "canon" in line.lower():
                return line
        # Fall back to the first device of any kind, if there's exactly one.
        devices = [l.strip() for l in out.stdout.splitlines() if l.strip()]
        if len(devices) == 1:
            return devices[0]
    except Exception:
        pass
    return None


def query_resolutions(device):
    """Ask the scanner which resolutions it supports; fall back to a list."""
    try:
        out = subprocess.run(
            ["scanimage", "--device", device, "--help"],
            capture_output=True, text=True, timeout=60,
        )
        m = re.search(r"--resolution\s+([0-9|]+)dpi", out.stdout)
        if m:
            vals = [v for v in m.group(1).split("|") if v]
            return sorted(set(vals), key=int)
    except Exception:
        pass
    return FALLBACK_RESOLUTIONS


class ScannerApp:
    def __init__(self, root):
        self.root = root
        root.title("Scanner")
        root.resizable(False, False)

        self.mode = tk.StringVar(value="Color")
        self.resolution = tk.StringVar(value=DEFAULT_RESOLUTION)
        self.fmt = tk.StringVar(value="PDF")
        self.outdir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value="Ready.")

        self._build_ui()
        # Populate the resolution list from the real device in the background
        # so the window appears instantly even if the scanner is waking up.
        threading.Thread(target=self._load_resolutions, daemon=True).start()

    # ---- UI ----------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self.root, padding=16)
        frm.grid(sticky="nsew")

        ttk.Label(frm, text="Mode").grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(
            frm, textvariable=self.mode, values=["Color", "Gray"],
            state="readonly", width=24,
        ).grid(row=0, column=1, **pad)

        ttk.Label(frm, text="Resolution (dpi)").grid(row=1, column=0, sticky="w", **pad)
        self.res_box = ttk.Combobox(
            frm, textvariable=self.resolution, values=FALLBACK_RESOLUTIONS,
            state="readonly", width=24,
        )
        self.res_box.grid(row=1, column=1, **pad)

        ttk.Label(frm, text="Format").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(
            frm, textvariable=self.fmt, values=["PDF", "Image (PNG)"],
            state="readonly", width=24,
        ).grid(row=2, column=1, **pad)

        ttk.Label(frm, text="Save to").grid(row=3, column=0, sticky="w", **pad)
        row = ttk.Frame(frm)
        row.grid(row=3, column=1, sticky="w", **pad)
        ttk.Entry(row, textvariable=self.outdir, width=18).grid(row=0, column=0)
        ttk.Button(row, text="…", width=3, command=self._pick_folder).grid(row=0, column=1, padx=(4, 0))

        self.scan_btn = ttk.Button(frm, text="Scan", command=self._start_scan)
        self.scan_btn.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)

        self.progress = ttk.Progressbar(frm, mode="indeterminate", length=260)
        self.progress.grid(row=5, column=0, columnspan=2, **pad)

        ttk.Label(frm, textvariable=self.status, foreground="#555").grid(
            row=6, column=0, columnspan=2, sticky="w", **pad
        )

    def _pick_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.outdir.get() or DEFAULT_OUTPUT_DIR)
        if chosen:
            self.outdir.set(chosen)

    def _load_resolutions(self):
        device = find_device()
        if not device:
            return
        res = query_resolutions(device)
        def apply():
            self.res_box["values"] = res
            if DEFAULT_RESOLUTION in res:
                self.resolution.set(DEFAULT_RESOLUTION)
            elif res:
                self.resolution.set(res[0])
        self.root.after(0, apply)

    # ---- scanning ----------------------------------------------------------
    def _start_scan(self):
        outdir = self.outdir.get().strip() or DEFAULT_OUTPUT_DIR
        if not os.path.isdir(outdir):
            messagebox.showerror("Scanner", f"Folder does not exist:\n{outdir}")
            return
        self.scan_btn.config(state="disabled")
        self.progress.start(12)
        self.status.set("Finding scanner…")
        threading.Thread(target=self._run_scan, args=(outdir,), daemon=True).start()

    def _run_scan(self, outdir):
        device = find_device()
        if not device:
            return self._finish(ok=False, msg="No scanner found. Is it plugged in and on?")

        is_pdf = self.fmt.get().startswith("PDF")
        ext = "pdf" if is_pdf else "png"
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(outdir, f"scan_{stamp}.{ext}")

        base = [
            "scanimage",
            "--mode", self.mode.get(),
            "--resolution", self.resolution.get(),
            "--format", "pdf" if is_pdf else "png",
            "-o", path,
        ]

        # The genesys USB address can go stale between lookup and open. Try the
        # resolved device first; if that fails, re-resolve; finally let SANE
        # auto-pick (no --device), which is the most robust when one scanner is
        # attached.
        attempts = [
            base[:1] + ["--device", device] + base[1:],
            None,            # placeholder: re-resolve just before this attempt
            base,            # auto-pick
        ]

        self._set_status("Scanning… (first scan warms up the lamp)")
        proc = None
        for i, cmd in enumerate(attempts):
            if cmd is None:
                redev = find_device()
                if not redev:
                    continue
                cmd = base[:1] + ["--device", redev] + base[1:]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            except subprocess.TimeoutExpired:
                return self._finish(ok=False, msg="Scan timed out.")
            except FileNotFoundError:
                return self._finish(ok=False, msg="`scanimage` not found. Run installer.sh first.")
            if proc.returncode == 0 and os.path.exists(path):
                subprocess.run(["open", "-R", path])  # reveal in Finder
                return self._finish(ok=True, msg=f"Saved: {os.path.basename(path)}")

        detail = ""
        if proc is not None:
            lines = (proc.stderr or proc.stdout or "").strip().splitlines()
            detail = lines[-1] if lines else ""
        self._finish(ok=False, msg=detail or "Scan failed.")

    # ---- thread-safe UI updates -------------------------------------------
    def _set_status(self, msg):
        self.root.after(0, lambda: self.status.set(msg))

    def _finish(self, ok, msg):
        def done():
            self.progress.stop()
            self.scan_btn.config(state="normal")
            self.status.set(msg)
            if not ok:
                messagebox.showerror("Scanner", msg)
        self.root.after(0, done)


def main():
    root = tk.Tk()
    ScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
