#!/usr/bin/env python3
"""
sane-scan-mac — a small native GUI for any SANE-supported scanner on macOS.

A thin, dependency-light frontend over SANE's `scanimage`. It lists the
scanners SANE can see, queries each one for its real capabilities (modes and
resolutions), and lets you scan to PDF or PNG. No proprietary driver, nothing
to pay for.

The USB address SANE reports (e.g. genesys:libusb:BBB:DDD) changes whenever a
scanner re-enumerates, so the chosen scanner is re-matched by vendor/model
right before every scan.
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
for _p in ("/opt/homebrew/bin", "/usr/local/bin"):
    if _p not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")

FALLBACK_RESOLUTIONS = ["75", "100", "150", "300", "600", "1200", "2400", "4800"]
FALLBACK_MODES = ["Color", "Gray"]
PREFERRED_MODE = "Color"
DEFAULT_RESOLUTION = "300"
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Desktop")


class Scanner:
    """One SANE device: its (volatile) name plus vendor/model labels."""

    def __init__(self, name, vendor="", model=""):
        self.name = name
        self.vendor = vendor.strip()
        self.model = model.strip()

    @property
    def label(self):
        text = " ".join(x for x in (self.vendor, self.model) if x)
        return text or self.name


def list_scanners():
    """Return a list of Scanner objects SANE currently sees."""
    scanners = []
    try:
        out = subprocess.run(
            ["scanimage", "-f", "%d|%v|%m%n"],
            capture_output=True, text=True, timeout=60,
        )
        for line in out.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            name = parts[0]
            vendor = parts[1] if len(parts) > 1 else ""
            model = parts[2] if len(parts) > 2 else ""
            scanners.append(Scanner(name, vendor, model))
    except Exception:
        pass
    return scanners


def resolve_device(target):
    """Re-find the live device name for `target` (a Scanner), matching by
    vendor/model so a shifted USB address is handled. Falls back to the stored
    name, then to any single available device."""
    current = list_scanners()
    if target is not None:
        for s in current:
            if s.vendor == target.vendor and s.model == target.model and (target.model or target.vendor):
                return s.name
        for s in current:
            if s.name == target.name:
                return s.name
    if len(current) == 1:
        return current[0].name
    return target.name if target else None


def query_capabilities(device):
    """Return (modes, resolutions) reported by a specific device."""
    modes, resolutions = list(FALLBACK_MODES), list(FALLBACK_RESOLUTIONS)
    try:
        out = subprocess.run(
            ["scanimage", "--device", device, "--help"],
            capture_output=True, text=True, timeout=60,
        )
        mm = re.search(r"--mode\s+([A-Za-z][A-Za-z|]*)", out.stdout)
        if mm:
            vals = [v for v in mm.group(1).split("|") if v]
            if vals:
                modes = vals
        rm = re.search(r"--resolution\s+([0-9|]+)dpi", out.stdout)
        if rm:
            vals = [v for v in rm.group(1).split("|") if v]
            if vals:
                resolutions = sorted(set(vals), key=int)
    except Exception:
        pass
    return modes, resolutions


class ScannerApp:
    def __init__(self, root):
        self.root = root
        root.title("Scan")
        root.resizable(False, False)

        self.scanners = []            # list[Scanner]
        self.selected = None          # Scanner

        self.device_label = tk.StringVar(value="Looking for scanners…")
        self.mode = tk.StringVar(value=PREFERRED_MODE)
        self.resolution = tk.StringVar(value=DEFAULT_RESOLUTION)
        self.fmt = tk.StringVar(value="PDF")
        self.outdir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.status = tk.StringVar(value="Ready.")

        self._build_ui()
        self.refresh_devices()

    # ---- UI ----------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self.root, padding=16)
        frm.grid(sticky="nsew")

        ttk.Label(frm, text="Scanner").grid(row=0, column=0, sticky="w", **pad)
        drow = ttk.Frame(frm)
        drow.grid(row=0, column=1, sticky="w", **pad)
        self.device_box = ttk.Combobox(
            drow, textvariable=self.device_label, state="readonly", width=22,
        )
        self.device_box.grid(row=0, column=0)
        self.device_box.bind("<<ComboboxSelected>>", self._on_device_change)
        ttk.Button(drow, text="⟳", width=3, command=self.refresh_devices).grid(
            row=0, column=1, padx=(4, 0)
        )

        ttk.Label(frm, text="Mode").grid(row=1, column=0, sticky="w", **pad)
        self.mode_box = ttk.Combobox(
            frm, textvariable=self.mode, values=FALLBACK_MODES,
            state="readonly", width=24,
        )
        self.mode_box.grid(row=1, column=1, **pad)

        ttk.Label(frm, text="Resolution (dpi)").grid(row=2, column=0, sticky="w", **pad)
        self.res_box = ttk.Combobox(
            frm, textvariable=self.resolution, values=FALLBACK_RESOLUTIONS,
            state="readonly", width=24,
        )
        self.res_box.grid(row=2, column=1, **pad)

        ttk.Label(frm, text="Format").grid(row=3, column=0, sticky="w", **pad)
        ttk.Combobox(
            frm, textvariable=self.fmt, values=["PDF", "Image (PNG)"],
            state="readonly", width=24,
        ).grid(row=3, column=1, **pad)

        ttk.Label(frm, text="Save to").grid(row=4, column=0, sticky="w", **pad)
        orow = ttk.Frame(frm)
        orow.grid(row=4, column=1, sticky="w", **pad)
        ttk.Entry(orow, textvariable=self.outdir, width=18).grid(row=0, column=0)
        ttk.Button(orow, text="…", width=3, command=self._pick_folder).grid(
            row=0, column=1, padx=(4, 0)
        )

        self.scan_btn = ttk.Button(frm, text="Scan", command=self._start_scan)
        self.scan_btn.grid(row=5, column=0, columnspan=2, sticky="ew", **pad)

        self.progress = ttk.Progressbar(frm, mode="indeterminate", length=280)
        self.progress.grid(row=6, column=0, columnspan=2, **pad)

        ttk.Label(frm, textvariable=self.status, foreground="#555").grid(
            row=7, column=0, columnspan=2, sticky="w", **pad
        )

    def _pick_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.outdir.get() or DEFAULT_OUTPUT_DIR)
        if chosen:
            self.outdir.set(chosen)

    # ---- device discovery --------------------------------------------------
    def refresh_devices(self):
        self.status.set("Looking for scanners…")
        self.scan_btn.config(state="disabled")
        threading.Thread(target=self._load_devices, daemon=True).start()

    def _load_devices(self):
        scanners = list_scanners()

        def apply():
            self.scanners = scanners
            labels = [s.label for s in scanners]
            self.device_box["values"] = labels
            if scanners:
                self.device_box.current(0)
                self.selected = scanners[0]
                self.scan_btn.config(state="normal")
                self.status.set(f"Found {len(scanners)} scanner(s).")
                self._load_capabilities(scanners[0])
            else:
                self.device_label.set("No scanners found")
                self.status.set("No scanner found. Plug it in, power on, click ⟳.")
        self.root.after(0, apply)

    def _on_device_change(self, _event=None):
        idx = self.device_box.current()
        if 0 <= idx < len(self.scanners):
            self.selected = self.scanners[idx]
            self._load_capabilities(self.selected)

    def _load_capabilities(self, scanner):
        self.status.set("Reading scanner capabilities…")
        threading.Thread(
            target=self._load_capabilities_worker, args=(scanner,), daemon=True
        ).start()

    def _load_capabilities_worker(self, scanner):
        device = resolve_device(scanner) or scanner.name
        modes, resolutions = query_capabilities(device)

        def apply():
            self.mode_box["values"] = modes
            self.mode.set(PREFERRED_MODE if PREFERRED_MODE in modes else modes[0])
            self.res_box["values"] = resolutions
            self.resolution.set(
                DEFAULT_RESOLUTION if DEFAULT_RESOLUTION in resolutions else resolutions[0]
            )
            self.status.set("Ready.")
        self.root.after(0, apply)

    # ---- scanning ----------------------------------------------------------
    def _start_scan(self):
        if not self.selected:
            messagebox.showerror("Scan", "No scanner selected.")
            return
        outdir = self.outdir.get().strip() or DEFAULT_OUTPUT_DIR
        if not os.path.isdir(outdir):
            messagebox.showerror("Scan", f"Folder does not exist:\n{outdir}")
            return
        self.scan_btn.config(state="disabled")
        self.progress.start(12)
        self.status.set("Preparing…")
        threading.Thread(target=self._run_scan, args=(outdir,), daemon=True).start()

    def _run_scan(self, outdir):
        target = self.selected
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

        def with_device(dev):
            return base[:1] + ["--device", dev] + base[1:]

        # Re-match the device (handles shifted USB address), then retry with a
        # fresh lookup, then fall back to auto-pick (no --device).
        dev = resolve_device(target) or target.name
        attempts = [with_device(dev), "RERESOLVE", base]

        self._set_status("Scanning… (first scan warms up the lamp)")
        proc = None
        for cmd in attempts:
            if cmd == "RERESOLVE":
                redev = resolve_device(target)
                if not redev:
                    continue
                cmd = with_device(redev)
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
                messagebox.showerror("Scan", msg)
        self.root.after(0, done)


def main():
    root = tk.Tk()
    ScannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
