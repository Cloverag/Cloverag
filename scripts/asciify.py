"""Greyscale array -> character grid.

Build-time only (needs numpy/pillow). The nightly workflow never imports this;
it only reads the SVGs these produce.
"""
import numpy as np

from svgkit import RAMP


def to_rows(lum: np.ndarray, mask: np.ndarray | None, cols: int,
            aspect: float = 0.48, coverage: float = 0.35,
            lo_pct: float = 2.0, hi_pct: float = 98.0,
            invert: bool = False, blank_below: int = 0) -> list[str]:
    """Downsample to a character grid.

    `mask` marks which pixels are subject rather than background. Contrast is
    stretched across the subject only — stretching across the whole frame lets
    a bright background eat the range and the face renders as a flat mid-tone.

    `blank_below` drops the faintest N ramp levels to spaces. On artwork with a
    plain light backdrop this is what separates subject from page: without it
    the background renders as an even field of dots and the portrait sits in a
    grey rectangle instead of on the README.
    """
    h, w = lum.shape
    if mask is None:
        mask = np.ones((h, w), bool)
    if mask.sum() < 16:
        raise ValueError("mask kept almost nothing — check the source image")

    lo, hi = np.percentile(lum[mask], [lo_pct, hi_pct])
    span = max(float(hi - lo), 1e-6)

    # Monospace cells are about twice as tall as wide, so the row count is the
    # column count scaled by the image aspect and this correction factor.
    rows = int(round(cols * (h / w) * aspect))
    cell_w, cell_h = w / cols, h / rows

    out = []
    for r in range(rows):
        y0 = int(r * cell_h)
        y1 = max(int((r + 1) * cell_h), y0 + 1)
        line = []
        for c in range(cols):
            x0 = int(c * cell_w)
            x1 = max(int((c + 1) * cell_w), x0 + 1)
            cell_mask = mask[y0:y1, x0:x1]
            cov = float(cell_mask.mean())
            if cov < coverage:
                line.append(" ")
                continue
            v = (float(lum[y0:y1, x0:x1][cell_mask].mean()) - lo) / span
            v = min(max(v, 0.0), 1.0)
            if invert:
                v = 1.0 - v
            idx = int(round(v * (len(RAMP) - 1)))
            if idx <= blank_below:
                line.append(" ")
                continue
            # A covered cell never renders as blank; blank means "not subject".
            line.append(RAMP[max(idx, 1)])
        out.append("".join(line).rstrip())

    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return out


def luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def cell_colours(rgb: np.ndarray, mask: np.ndarray | None, cols: int,
                 rows: int, palette: int = 10) -> list[list[str]]:
    """Average colour per character cell, quantised to a small palette.

    Quantising is not only about file size. Long runs of one colour are what
    keep this from becoming per-character noise: flat artwork collapses into a
    handful of regions, and the result reads as the drawing rather than as
    static. It is also what makes run-length encoding worthwhile — without it
    every character needs its own <tspan>.
    """
    from PIL import Image

    h, w, _ = rgb.shape
    if mask is None:
        mask = np.ones((h, w), bool)
    cell_h, cell_w = h / rows, w / cols

    means = np.zeros((rows, cols, 3), np.uint8)
    for r in range(rows):
        y0 = int(r * cell_h)
        y1 = max(int((r + 1) * cell_h), y0 + 1)
        for c in range(cols):
            x0 = int(c * cell_w)
            x1 = max(int((c + 1) * cell_w), x0 + 1)
            m = mask[y0:y1, x0:x1]
            block = rgb[y0:y1, x0:x1]
            sel = block[m] if m.any() else block.reshape(-1, 3)
            means[r, c] = np.clip(sel.mean(axis=0), 0, 255).astype(np.uint8)

    small = Image.fromarray(means, "RGB").quantize(colors=palette, method=Image.MEDIANCUT)
    pal = small.getpalette()
    idx = np.asarray(small)
    table = [_readable(pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2])
             for i in range(palette)]
    return [[table[i] for i in row] for row in idx]


def _readable(r: int, g: int, b: int,
              band: tuple[float, float] = (0.40, 0.72),
              sat_boost: float = 1.45) -> str:
    """Keep the hue, force the brightness into a legible band.

    Text is thin: a colour lifted straight off the source paints near-black
    glyphs on a near-black README and the drawing disappears. Hue and
    saturation are what make it read as *that* image, so those survive; value
    gets remapped into a mid band that holds up on a white ground and a
    #0d1117 one alike, which is what lets a single file serve both themes.

    The band is deliberately narrow and central. Anything brighter washes out
    on white, anything darker sinks into the dark theme, and one file has to
    survive both — so saturation, not lightness, is what carries the contrast.
    """
    import colorsys

    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    lo, hi = band
    v = lo + v * (hi - lo)
    s = min(s * sat_boost, 1.0)
    r2, g2, b2 = colorsys.hsv_to_rgb(h, s, v)
    return f"#{round(r2 * 255):02x}{round(g2 * 255):02x}{round(b2 * 255):02x}"
