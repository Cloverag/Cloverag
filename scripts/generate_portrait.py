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
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

from asciify import luminance, to_rows  # noqa: E402
from svgkit import (CHAR_W, FONT_SIZE, LINE_H, ROOT, THEME, svg,  # noqa: E402
                    typed_rows)

# Below about 88 columns the face muddies; much above it and the block
# dominates the page.
COLS = 90
DISPLAY_W = 460


def cutout(img: Image.Image, use_rembg: bool):
    """Subject mask.

    An image that already carries alpha needs no model — use it directly. That
    covers sprites and cut-out PNGs, where converting to RGB first would turn
    every transparent pixel black and mark the whole frame as subject.
    """
    if img.mode == "RGBA":
        alpha = np.asarray(img)[:, :, 3]
        if alpha.min() < 128:
            print(f"using the image's own alpha channel "
                  f"({(alpha > 128).mean():.0%} opaque)")
            return alpha > 128
    if not use_rembg:
        return None
    try:
        from rembg import remove
    except ImportError:
        print("rembg not installed — continuing without a subject mask")
        return None
    out = remove(img.convert("RGBA"))
    return np.asarray(out)[:, :, 3] > 128


def parse_crop(spec: str, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """`l,t,r,b` as fractions of the frame, e.g. 0.24,0.03,0.70,0.50."""
    parts = [float(v) for v in spec.split(",")]
    if len(parts) != 4:
        raise ValueError("crop needs four comma-separated fractions: l,t,r,b")
    w, h = size
    l, t, r, b = parts
    return (int(w * l), int(h * t), int(w * r), int(h * b))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo")
    ap.add_argument("--crop", help="l,t,r,b as fractions of the frame. Crop "
                                   "tight: a face filling 30%% of the frame "
                                   "only gets ~30 characters across.")
    ap.add_argument("--invert", action="store_true",
                    help="the source is a dark subject on a light background "
                         "(ink drawings, manga, anything on white). Describes "
                         "the light-theme rendering; the dark variant flips it.")
    ap.add_argument("--blank", type=int, default=0, metavar="N",
                    help="render the N faintest ramp levels as empty space")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--rembg", action="store_true",
                    help="segment the subject with rembg (~176 MB model, once)")
    ap.add_argument("--name", default="portrait",
                    help="basename; writes <name>-light.svg and <name>-dark.svg")
    args = ap.parse_args()

    src = Path(args.photo)
    if not src.exists():
        print(f"no such photo: {src}")
        return 1

    img = Image.open(src)
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")

    if args.crop:
        img = img.crop(parse_crop(args.crop, img.size))
    if min(img.size) < 900:
        print(f"note: {img.size[0]}x{img.size[1]} is under 900px. Fine for flat "
              f"artwork; on a photo expect thin features to average away.")

    mask = cutout(img, args.rembg)
    lum = luminance(np.asarray(img.convert("RGB")).astype(np.float64))

    # Density is the encoding, and it does not survive a colour swap. On a dark
    # page the ink is light, so the lit side of the subject has to be the dense
    # side or the face reads as a hole. On a light page the ink is dark and the
    # ramp has to run the other way. Two renderings, one per theme.
    for theme, flip in (("light", args.invert), ("dark", not args.invert)):
        rows = to_rows(lum, mask, cols=args.cols, invert=flip,
                       coverage=0.2, blank_below=args.blank)
        width = args.cols * CHAR_W
        top = LINE_H
        height = top + len(rows) * LINE_H + LINE_H * 0.6
        css = (
            f".r{{font-family:'JBMramp',monospace;font-size:{FONT_SIZE}px;"
            f"fill:{THEME[theme]['ink']};white-space:pre;}}"
            # One fill colour. Per-character rainbow colouring is what makes
            # most ASCII portraits look like static.
            + f".cur{{fill:{THEME[theme]['accent']};}}"
        )
        body = typed_rows(rows, x=0, y0=top)
        out = ROOT / "assets" / f"{args.name}-{theme}.svg"
        out.write_text(svg(width, height, body, css, "portrait, drawn in ASCII",
                           fonts=("ramp",), display_width=DISPLAY_W,
                           theme_switch=False))
        total = (len(rows) - 1) * 0.09 + 0.55
        print(f"{out.relative_to(ROOT)}  {len(rows)} rows x {args.cols} cols  "
              f"{out.stat().st_size / 1024:.1f} KB  types in {total:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
