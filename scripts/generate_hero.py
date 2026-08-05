"""The hero wordmark: my name, rasterised from JetBrains Mono, re-drawn in the
portrait's own 13-character ramp, typing itself in.

Build-time only, and the output is committed — the nightly job never touches it.

    python3 scripts/generate_hero.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asciify import luminance, to_rows  # noqa: E402
from svgkit import (CHAR_W, FONT_SIZE, LINE_H, ROOT, svg,  # noqa: E402
                    typed_rows)

TEXT = "raghav"
COLS = 74
DISPLAY_W = 460


def raster(text: str, ttf: Path) -> np.ndarray:
    """Render text huge, then trim to the ink. Rendering large and downsampling
    into the grid keeps the letterform edges from breaking up — the same reason
    the portrait wants a 1200px source rather than a 320px one."""
    font = ImageFont.truetype(str(ttf), 320)
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    l, t, r, b = probe.textbbox((0, 0), text, font=font)
    pad = 24
    img = Image.new("L", (r - l + pad * 2, b - t + pad * 2), 0)
    ImageDraw.Draw(img).text((pad - l, pad - t), text, font=font, fill=255)
    arr = np.asarray(img)
    ys, xs = np.nonzero(arr > 8)
    return arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def main() -> int:
    ttf = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not ttf or not ttf.exists():
        print("usage: generate_hero.py <path/to/JetBrainsMono-Regular.ttf>")
        return 1

    ink = raster(TEXT, ttf).astype(np.float64)
    lum = np.stack([ink] * 3, axis=2)
    # Every lit pixel is subject; the glyph interiors carry the tone.
    mask = ink > 8
    rows = to_rows(luminance(lum), mask, cols=COLS, coverage=0.12,
                   lo_pct=0.0, hi_pct=100.0)

    width = COLS * CHAR_W
    top = LINE_H
    height = top + len(rows) * LINE_H + LINE_H * 0.6

    css = (
        f".r{{font-family:'JBMramp',monospace;font-size:{FONT_SIZE}px;"
          "fill:var(--accent);white-space:pre;}"
        + ".cur{fill:var(--accent);}"
    )
    body = typed_rows(rows, x=0, y0=top)
    out = ROOT / "assets" / "hero.svg"
    out.write_text(svg(width, height, body, css, f"{TEXT} — typed in ASCII",
                       fonts=("ramp",), display_width=DISPLAY_W))
    total = (len(rows) - 1) * 0.09 + 0.55
    print(f"{out.relative_to(ROOT)}  {len(rows)} rows x {COLS} cols  "
          f"{out.stat().st_size / 1024:.1f} KB  types in {total:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
