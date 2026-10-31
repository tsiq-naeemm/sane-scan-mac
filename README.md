# sane-scan-mac

**Scan with any scanner on your Mac — free, native, no VueScan.**

A tiny, open-source GUI for using **any [SANE](http://www.sane-project.org/)-supported scanner on macOS and Apple Silicon**. It wraps SANE's `scanimage` in a simple window: pick your scanner, choose a mode/resolution, and scan to PDF or PNG. No proprietary driver, nothing to pay for.

> Works great with the **Canon LiDE 110** and hundreds of other SANE-supported scanners (Canon, Epson, HP, Brother, Fujitsu…) — including models Apple dropped support for on modern macOS.

## Why this exists

Many perfectly good scanners (like the Canon LiDE 110) have no working driver on modern Apple Silicon Macs. Commercial apps like VueScan solve it but cost money. SANE already contains free, community-maintained drivers for these devices — this project just gives them a friendly macOS front-end.

## Install

```bash
git clone https://github.com/tsiq-naeemm/sane-scan-mac.git
cd sane-scan-mac
chmod +x installer.sh Scanner.command
./installer.sh
```

The installer sets up Homebrew (if needed), `sane-backends` (the actual drivers), and `python-tk` (for the GUI), then checks that a scanner is detected.

## Use

Double-click **`Scanner.command`** in Finder.
(The very first time, right-click it → **Open** to clear Gatekeeper.)

Options:

- **Scanner** — pick from every scanner SANE detects (⟳ to rescan)
- **Mode** — populated from your scanner (Color / Gray / Lineart / …), defaults to Color
- **Resolution** — populated from your scanner, defaults to 300 dpi
- **Format** — PDF (default) or Image (PNG)
- **Save to** — output folder (default: Desktop)

Scans are named `scan_YYYYMMDD_HHMMSS.pdf` (or `.png`) and revealed in Finder when done. Everything else uses the SANE backend defaults.

## Command-line equivalent

If you ever want it without the GUI:

```bash
scanimage --mode Color --resolution 300 --format=pdf -o ~/Desktop/scan.pdf
```

## Notes

- The first scan after idle is slow — the lamp warms up and calibrates.
- A scanner's USB address can change between scans; the GUI re-matches your
  chosen scanner by vendor/model each time, so you don't have to worry about it.

## Requirements

- macOS (Intel or Apple Silicon)
- [Homebrew](https://brew.sh) (the installer can set it up for you)
- A scanner with a [SANE backend](http://www.sane-project.org/sane-mfgs.html) — check the list to confirm yours is supported.

## How it works (no reverse engineering required)

SANE's open-source backends already speak these scanners' protocols — work the
community did years ago. `sane-scan-mac` is just a thin, convenient GUI on top.

## License

MIT
