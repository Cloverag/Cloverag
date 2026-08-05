"""Photo -> ASCII portrait SVG, typing itself in.

Build-time only; the output is committed and the nightly job never touches it.

    pip install pillow numpy rembg onnxruntime   # rembg is optional
    python3 scripts/generate_portrait.py photo.jpg

The first rembg run downloads a ~176 MB background-removal model. Once, then
cached. Without rembg installed this falls back to no mask, which is fine for
a photo already shot on a plain backdrop.

The photo decides everything. No parameter tuning rescues a bad input, because
ASCII draws with shadow rather than detail — there are 13 brightness levels to
work with and that is all:

  * Side light, a window at roughly 45 degrees and everything else off. Flat
    frontal light gives a uniform mid-tone and the face renders as a hole.
  * Crop tight, chin to just above the hair. At 90 columns a face filling 30%
    of the frame gets about 30 characters and the eyes will not resolve.
  * 1200px or more. Thin features — glasses frames — average away on downscale
    from anything smaller.
  * Plain background, and do not wear black against a dark wall. If the subject
    and the backdrop share a value, no amount of masking separates them.
  * Slight angle rather than dead-on, so the nose and jaw get a shadow edge.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asciify import luminance, to_rows  # noqa: E402
from svgkit import CHAR_W, FONT_SIZE, LINE_H, ROOT, svg, typed_rows  # noqa: E402

# Below about 88 columns the face muddies; much above it and the block
# dominates the page.
COLS = 90
DISPLAY_W = 460


def cutout(img: Image.Image):
    """Subject mask via rembg, or None if it isn't installed."""
    try:
        from rembg import remove
    except ImportError:
        print("rembg not installed — continuing without a subject mask")
        return None
    out = remove(img.convert("RGBA"))
    alpha = np.asarray(out)[:, :, 3]
    return alpha > 128


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"no such photo: {src}")
        return 1

    img = Image.open(src).convert("RGB")
    if min(img.size) < 900:
        print(f"warning: {img.size[0]}x{img.size[1]} is small — expect thin "
              f"features to disappear. 1200px+ on the short edge is safer.")

    mask = cutout(img)
    rows = to_rows(luminance(np.asarray(img).astype(np.float64)), mask, cols=COLS)

    width = COLS * CHAR_W
    top = LINE_H
    height = top + len(rows) * LINE_H + LINE_H * 0.6

    css = (
        f".r{{font-family:'JBMramp',monospace;font-size:{FONT_SIZE}px;"
        "fill:var(--ink);white-space:pre;}"
        # One fill colour. Per-character rainbow colouring is what makes most
        # ASCII portraits look like static.
        + ".cur{fill:var(--accent);}"
    )
    body = typed_rows(rows, x=0, y0=top)
    out = ROOT / "assets" / "portrait.svg"
    out.write_text(svg(width, height, body, css, "portrait, drawn in ASCII",
                       fonts=("ramp",), display_width=DISPLAY_W))
    total = (len(rows) - 1) * 0.09 + 0.55
    print(f"{out.relative_to(ROOT)}  {len(rows)} rows x {COLS} cols  "
          f"{out.stat().st_size / 1024:.1f} KB  types in {total:.1f}s")
    print("swap assets/hero.svg for assets/portrait.svg in README.md to use it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
