# LiDE 110 Scanner — macOS

A free, open-source way to use a Canon LiDE 110 (and most SANE-supported
scanners) on modern Apple Silicon Macs. It's a thin GUI over SANE's
`scanimage`, so there's no proprietary driver and nothing to pay for.

## Install

```bash
cd lide110-scanner
chmod +x installer.sh Scanner.command
./installer.sh
```

The installer sets up Homebrew (if needed), `sane-backends` (the actual
driver), and `python-tk` (for the GUI), then checks that your scanner is
detected.

## Use

Double-click **`Scanner.command`** in Finder.
(The very first time, right-click it → **Open** to clear Gatekeeper.)

Options:

- **Mode** — Color (default) or Gray
- **Resolution** — populated from what your scanner reports (default 300 dpi)
- **Format** — PDF (default) or Image (PNG)
- **Save to** — output folder (default: Desktop)

Everything else uses the SANE backend defaults. Scans are named
`scan_YYYYMMDD_HHMMSS.pdf` (or `.png`) and revealed in Finder when done.

## Notes

- The first scan after idle is slow — the lamp warms up and calibrates.
- The USB address can change between scans; the GUI re-resolves it each time,
  so you don't need to worry about it.
- Command-line equivalent, if you ever want it:
  ```bash
  scanimage --mode Color --resolution 300 --format=pdf -o ~/Desktop/scan.pdf
  ```

## How this works (no reverse engineering required)

The Canon LiDE 110 uses Canon's GL124 chipset, supported for years by SANE's
open-source `genesys` backend. This project just makes that convenient.
