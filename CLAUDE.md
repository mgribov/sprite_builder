# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A dual-mode sprite tool consisting of two standalone files:
- **`index.html`** — Browser-based sprite editor and builder (single-file SPA, ~1,245 lines, vanilla JS)
- **`sprite_builder_native.py`** — CLI sprite sheet generator (Python, ~386 lines, requires Pillow)

No build step is needed for `index.html`. Open it directly in a browser.

## Running the Python Tool

```bash
pip install Pillow
python sprite_builder_native.py <image_dir> <output_dir> [--retina] [--gap N]
```

Optional external PNG optimizers (auto-detected): `pngquant`, `oxipng`, `optipng`.

## Architecture

### index.html (Web App)

Single global state object tracks canvas, zoom/pan, selection bounds, undo/redo stacks, and replacement preview. No framework — all DOM manipulation and rendering is manual.

**Two modes:**
- **Editor mode** — Load a PNG, select a rectangular region, replace it with another image (stretch/center/contain fit), export result.
- **Builder mode** — Add multiple PNG files or folders, pack them into a sprite sheet using MaxRects, generate PNG output and CSS class definitions.

**Key subsystems:**
- Canvas rendering with zoom (0.1×–64×) and pan; coordinate transforms via `screenToImage()` / `imageToScreen()`
- MaxRects bin packing (lines ~1082–1175): tries multiple widths, caches results, returns optimal packing
- Undo/redo stack (max 40 states) backed by `ImageData` snapshots
- File I/O via `FileReader` API and `Blob`/`URL.createObjectURL` for downloads

### sprite_builder_native.py (Python CLI)

Same MaxRects algorithm (lines 39–120) with best-area-fit scoring, rectangle splitting, and free-rect pruning. Doubles bin size automatically if packing fails.

**Output pipeline:**
1. Load PNGs from directory → convert to RGBA
2. Pack with MaxRects
3. Try multiple PNG encoding strategies (RGB, RGBA, palette/indexed) and pick smallest
4. Optionally run external optimizer
5. Write sprite PNG(s) and CSS file

Retina support: upscale source images 2× before packing, output both normal and `@2x` variants.
