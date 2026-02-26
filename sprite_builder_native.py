#!/usr/bin/env python3
"""
sprite_builder_native.py
------------------------
Build a tightly‑packed PNG sprite sheet + retina copy + CSS
without any third‑party packing library.
"""

import argparse
import io
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image

# --------------------------------------------------------------------- #
# Configuration – feel free to tweak
# --------------------------------------------------------------------- #
SRC_DIR = Path("./images")          # folder that contains PNGs
OUT_DIR = Path("./dist")            # folder for sprite.png, sprite@2x.png, sprite.css
RETINA_FACTOR = 2                   # 2× high‑res sprite

# --------------------------------------------------------------------- #
# Helper: load all PNGs (name, image, width, height)
# --------------------------------------------------------------------- #
def load_images(src: Path):
    imgs = []
    for p in sorted(src.glob("*.png")):
        im = Image.open(p).convert("RGBA")
        imgs.append((p.stem, im, im.width, im.height))
    return imgs


# --------------------------------------------------------------------- #
# -----  Simple MaxRects bin packing ----------------------------------
# --------------------------------------------------------------------- #
class MaxRectsBin:
    """MaxRects bin packing (Best Area Fit) – handles overlapping free rects."""
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        # a free rectangle is (x, y, w, h)
        self.free_rects = [(0, 0, width, height)]

    def place(self, w: int, h: int):
        """Place a rectangle of size (w, h). Returns (x, y) or None."""
        best_rect = None
        best_score = None

        for fr in self.free_rects:
            fw, fh = fr[2], fr[3]
            if w <= fw and h <= fh:
                score = fw * fh - w * h  # minimal waste
                if best_score is None or score < best_score:
                    best_score = score
                    best_rect = fr

        if best_rect is None:
            return None

        x, y = best_rect[0], best_rect[1]
        placed = (x, y, w, h)

        # Split *every* free rect that overlaps with the placed rect
        new_free = []
        for fr in self.free_rects:
            if self._overlaps(fr, placed):
                new_free.extend(self._split(fr, placed))
            else:
                new_free.append(fr)
        self.free_rects = new_free
        self._prune()

        return (x, y)

    @staticmethod
    def _overlaps(a, b):
        """Check if two (x, y, w, h) rectangles overlap."""
        return (a[0] < b[0] + b[2] and a[0] + a[2] > b[0] and
                a[1] < b[1] + b[3] and a[1] + a[3] > b[1])

    @staticmethod
    def _split(free, used):
        """Split *free* into up to 4 parts that don't overlap *used*."""
        fx, fy, fw, fh = free
        ux, uy, uw, uh = used
        parts = []
        # Left strip
        if ux > fx:
            parts.append((fx, fy, ux - fx, fh))
        # Right strip
        if ux + uw < fx + fw:
            parts.append((ux + uw, fy, (fx + fw) - (ux + uw), fh))
        # Top strip
        if uy > fy:
            parts.append((fx, fy, fw, uy - fy))
        # Bottom strip
        if uy + uh < fy + fh:
            parts.append((fx, uy + uh, fw, (fy + fh) - (uy + uh)))
        return parts

    def _prune(self):
        """Remove any free rect fully contained inside another."""
        pruned = []
        for i, a in enumerate(self.free_rects):
            contained = False
            for j, b in enumerate(self.free_rects):
                if i == j:
                    continue
                if (a[0] >= b[0] and a[1] >= b[1] and
                    a[0] + a[2] <= b[0] + b[2] and
                    a[1] + a[3] <= b[1] + b[3]):
                    contained = True
                    break
            if not contained:
                pruned.append(a)
        self.free_rects = pruned


# --------------------------------------------------------------------- #
# Pack all icons into the tightest possible bin.
# Returns (packed_list, final_width, final_height)
# packed_list contains (name, image, x, y, w, h)
# --------------------------------------------------------------------- #
def pack_rectangles(imgs):
    total_area = sum(w * h for _, _, w, h in imgs)
    max_img_w = max(w for _, _, w, h in imgs)
    max_img_h = max(h for _, _, w, h in imgs)
    # start with a square roughly equal to sqrt(area), but at least
    # as large as the biggest single image
    side = int(math.sqrt(total_area)) + 1
    width = max(side, max_img_w)
    height = max(side, max_img_h)

    # Sort by largest side first – a common heuristic
    sorted_imgs = sorted(imgs, key=lambda t: max(t[2], t[3]), reverse=True)

    while True:
        bin = MaxRectsBin(width, height)
        placed = []
        success = True

        for name, im, w, h in sorted_imgs:
            pos = bin.place(w, h)
            if pos is None:
                success = False
                break
            placed.append((name, im, pos[0], pos[1], w, h))

        if success:
            break

        # If it failed, enlarge the bin and try again
        if width <= height:
            width *= 2
        else:
            height *= 2

    # placed = (name, im, x, y, w, h)
    final_w = max(p[2] + p[4] for p in placed)   # x + w
    final_h = max(p[3] + p[5] for p in placed)   # y + h

    return placed, final_w, final_h


# --------------------------------------------------------------------- #
# Create a sprite from the packed layout
# --------------------------------------------------------------------- #
def make_sprite(packed_imgs, sprite_w, sprite_h, upscale=1, bg=(0, 0, 0, 0)):
    out_w, out_h = sprite_w * upscale, sprite_h * upscale
    sprite = Image.new("RGBA", (out_w, out_h), bg)

    # List of (name, x, y) for CSS – negative values for background‑position
    positions = []

    for name, im, x, y, w, h in packed_imgs:
        if upscale > 1:
            im = im.resize((w * upscale, h * upscale), Image.NEAREST)

        sprite.paste(im, (x * upscale, y * upscale), im)
        positions.append((name, -x, -y))

    return sprite, positions


# --------------------------------------------------------------------- #
# Generate the CSS file
# --------------------------------------------------------------------- #
def generate_css(positions, sprite_w, sprite_h, max_w, max_h,
                  normal_name, retina_name):
    css = []

    css.append(".sprite {")
    css.append(f"  background-image: url('{normal_name}');")
    css.append("  background-repeat: no-repeat;")
    css.append("  display: inline-block;")
    css.append(f"  width: {max_w}px;")
    css.append(f"  height: {max_h}px;")
    css.append("}\n")

    css.append(".retina {")
    css.append(f"  background-image: url('{retina_name}');")
    css.append(f"  background-size: {sprite_w}px {sprite_h}px;")
    css.append("}\n")

    for name, x, y in positions:
        css.append(f".icon-{name} {{")
        css.append(f"  background-position: {x}px {y}px;")
        css.append("}\n")

    return "\n".join(css)


# --------------------------------------------------------------------- #
# PNG optimisation – pick the smallest encoding strategy
# --------------------------------------------------------------------- #
def _uses_alpha(img):
    """Return True if any pixel has alpha < 255."""
    if img.mode != "RGBA":
        return False
    return img.getchannel("A").getextrema()[0] < 255


def _png_bytes(img):
    """Render *img* to an in-memory PNG with max Pillow compression."""
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _try_external_crush(path):
    """Optionally re-compress with external tools if available.

    Tried in order:
      1. pngquant  – lossy palette (quality ≥ 90, skipped if quality drops)
      2. oxipng    – lossless re-encode   (preferred)
      3. optipng   – lossless re-encode   (fallback)
    Each tool only overwrites the file if the result is smaller.
    """
    # --- lossy quantisation (high quality, keeps only if smaller) ---
    pngquant = shutil.which("pngquant")
    if pngquant:
        tmp = str(path) + ".pqtmp"
        res = subprocess.run(
            [pngquant, "--quality=90-100", "--speed=1",
             "--strip", "--output", tmp, "--force", str(path)],
            capture_output=True,
        )
        tmp_p = Path(tmp)
        if res.returncode == 0 and tmp_p.exists() and tmp_p.stat().st_size < path.stat().st_size:
            tmp_p.replace(path)
        else:
            tmp_p.unlink(missing_ok=True)

    # --- lossless re-compression ---
    oxipng = shutil.which("oxipng")
    if oxipng:
        subprocess.run(
            [oxipng, "-o", "4", "--strip", "safe", "-q", str(path)],
            capture_output=True,
        )
        return

    optipng = shutil.which("optipng")
    if optipng:
        subprocess.run(
            [optipng, "-o7", "-strip", "all", "-quiet", str(path)],
            capture_output=True,
        )


def optimize_and_save(img, path):
    """Save *img* as the smallest possible PNG.

    Strategy:
      1. Drop the alpha channel entirely when it is unused.
      2. Try true-colour (RGB / RGBA) with max zlib compression.
      3. Try palette (indexed) mode – lossless when ≤ 256 unique colours,
         lossy 256-colour quantisation otherwise.
      4. Write whichever is smallest.
      5. Optionally re-crush with pngquant / oxipng / optipng.
    """
    has_alpha = _uses_alpha(img)
    base = img if has_alpha else img.convert("RGB")

    candidates = {}

    # --- true-colour ---
    candidates["truecolor"] = _png_bytes(base)

    # --- palette / indexed ---
    try:
        unique = base.getcolors(maxcolors=256)
        if unique is not None:
            # ≤ 256 unique colours → effectively lossless
            pal = base.quantize(colors=256, dither=0)
        else:
            # > 256 colours → lossy quantisation (no dither for crisp edges)
            pal = base.quantize(colors=256, dither=0)
        candidates["palette"] = _png_bytes(pal)
    except Exception:
        pass  # quantize can fail on some edge-case images

    best_name = min(candidates, key=lambda k: len(candidates[k]))
    best_data = candidates[best_name]

    path = Path(path)
    path.write_bytes(best_data)

    # optional external crush (only overwrites if smaller)
    _try_external_crush(path)

    final_size = path.stat().st_size
    return best_name, final_size


# --------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Packed sprite builder – native implementation")
    parser.add_argument("--src", type=Path, default=SRC_DIR,
                        help="folder containing PNG icons")
    parser.add_argument("--out", type=Path, default=OUT_DIR,
                        help="output folder")
    args = parser.parse_args()

    src = args.src
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    imgs = load_images(src)
    if not imgs:
        print(f"No PNG files found in {src}")
        return

    print(f"Loaded {len(imgs)} PNGs.")

    # 1️⃣ Pack the icons
    packed, sprite_w, sprite_h = pack_rectangles(imgs)
    print(f"Sprite size (normal): {sprite_w}×{sprite_h} px")

    # 2️⃣ Normal sprite
    normal_sprite, positions = make_sprite(packed, sprite_w, sprite_h, upscale=1)
    normal_path = out / "sprite.png"
    strategy, size = optimize_and_save(normal_sprite, normal_path)
    print(f"Saved normal sprite: {normal_path}  ({size:,} bytes, {strategy})")

    # 3️⃣ Retina sprite
    retina_sprite, _ = make_sprite(packed, sprite_w, sprite_h, upscale=RETINA_FACTOR)
    retina_path = out / "sprite@2x.png"
    strategy, size = optimize_and_save(retina_sprite, retina_path)
    print(f"Saved retina sprite: {retina_path}  ({size:,} bytes, {strategy})")

    # 4️⃣ CSS
    # We use the maximum width / height of any icon as the element size
    max_w = max(w for _, _, w, _ in imgs)
    max_h = max(h for _, _, _, h in imgs)

    css_text = generate_css(
        positions,
        sprite_w,
        sprite_h,
        max_w,
        max_h,
        normal_name="sprite.png",
        retina_name="sprite@2x.png",
    )
    css_path = out / "sprite.css"
    css_path.write_text(css_text, encoding="utf-8")
    print(f"Saved CSS: {css_path}")

    print("\n--- Example usage ---")
    print("<link rel=\"stylesheet\" href=\"dist/sprite.css\">\n")
    print("<!-- Normal resolution -->")
    print("<div class=\"sprite icon-home\"></div>\n")
    print("<!-- Retina resolution -->")
    print("<div class=\"sprite retina icon-home\"></div>\n")
    print("All set!")


if __name__ == "__main__":
    main()

