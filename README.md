# PNG Sprite Builder and Editor

A simple, fully local tool for building and editing PNG sprite sheets. All processing happens in your browser or on your machine — data never leaves your computer.

Try it: [https://sprite-editor.scrapester.com/](https://sprite-editor.scrapester.com/)

Two ways to use it:

- **`index.html`** — open in any browser, no install needed
- **`sprite_builder_native.py`** — run from the command line for batch processing

---

## Browser tool (`index.html`)

Just open the file in your browser. No server, no dependencies.

### Edit an existing sprite

1. Click **Open Sprite** (or drag and drop a PNG onto the canvas)
2. Click and drag on the canvas to select a region
3. Click **Replace Selection** and pick a replacement image
4. Choose a fit mode: **Stretch**, **Center**, or **Contain**
5. Click **Export PNG** to download the result

### Build a new sprite sheet

1. Click **Add Images** or **Add Folder** to load your PNGs
2. Set a **Gap** (padding between images) if needed
3. Click **Generate Sprite** — the packed sheet appears on the canvas
4. Click **Export PNG** to download the sprite
5. Click **Export CSS** to download a ready-to-use CSS file

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Delete` | Clear selected region |
| `Escape` | Clear selection |
| `0` | Zoom to fit |
| `+` / `-` | Zoom in / out |

**Panning:** middle-click and drag, or Alt+drag.

**Zoom:** scroll wheel or the zoom controls in the bottom-right corner.

**Drag and drop:** drop a PNG onto the canvas to open it as a sprite. If a region is already selected, the dropped image replaces the selection instead.

---

## Command-line tool (`sprite_builder_native.py`)

### Requirements

```bash
pip install Pillow
```

Optional (auto-detected, used if available):

- **`pngquant`** — lossy palette compression
- **`oxipng`** or **`optipng`** — lossless PNG re-encoding

### Usage

```bash
python sprite_builder_native.py --src ./images --out ./dist
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--src` | `./images` | Folder containing PNG files |
| `--out` | `./dist` | Output folder |

### Output

| File | Description |
|------|-------------|
| `sprite.png` | Normal-resolution sprite sheet |
| `sprite@2x.png` | Retina (2×) sprite sheet |
| `sprite.css` | CSS with `.sprite`, `.retina`, and `.icon-<name>` classes |

### Using the generated CSS

```html
<link rel="stylesheet" href="dist/sprite.css">

<!-- Normal resolution -->
<div class="sprite icon-home"></div>

<!-- Retina resolution -->
<div class="sprite retina icon-home"></div>
```

CSS class names are derived from the PNG filenames (without extension). The `.icon-<name>` class sets `background-position`; `.sprite` sets the shared image URL and dimensions; `.retina` switches to the `@2x` image and adjusts `background-size`.

---

## How packing works

Both tools use the **MaxRects** bin packing algorithm. Images are sorted by their largest dimension and placed greedily into a bin, splitting remaining free space into up to four rectangles after each placement. The browser tool additionally tries multiple candidate bin widths and picks the layout with the smallest total area.

The Python tool picks the smallest PNG encoding for each output (RGB vs RGBA vs indexed/palette) before optionally passing the file to an external optimizer.
