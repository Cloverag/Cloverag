"""Section headings as SVG.

This is the only way to put your own typeface on a heading — GitHub strips
<style>, style="", class="", <font> and inline <svg> from README markdown, so
the alternative is its default sans and nothing else.

Stated plainly: image headings have no anchor links, so the README outline in
GitHub's sidebar goes empty. The alt text carries the word for screen readers.
That is a real cost, taken deliberately.

    python3 scripts/generate_headings.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from svgkit import ROOT, esc, svg  # noqa: E402

HEADINGS = ["work", "stack", "activity", "elsewhere"]

WIDTH = 840.0
HEIGHT = 34.0
SIZE = 15.0
TRACK = 3.2  # letter-spacing; a wide-tracked lowercase mono reads as a label


def build(word: str) -> str:
    css = (
        f".h{{font-family:'JBMui',monospace;font-size:{SIZE}px;fill:var(--ink);"
          f"letter-spacing:{TRACK}px;}}"
        + ".rule{stroke:var(--rule);stroke-width:1;}"
        + ".tick{fill:var(--accent);}"
    )
    # Advance width is 0.600 em and letter-spacing adds a gap after every
    # character, so the rule can start at an exactly known x.
    text_w = len(word) * (SIZE * 0.600 + TRACK)
    bar_x = 0.0
    label_x = bar_x + 14.0
    rule_x = label_x + text_w + 12.0
    baseline = HEIGHT / 2 + SIZE * 0.36

    body = (
        f'<rect class="tick" x="{bar_x}" y="{HEIGHT / 2 - 6:.1f}" width="4" height="12"/>'
        f'<text class="h" x="{label_x:.1f}" y="{baseline:.1f}">{esc(word)}</text>'
        f'<line class="rule" x1="{rule_x:.1f}" y1="{HEIGHT / 2:.1f}" '
        f'x2="{WIDTH:.1f}" y2="{HEIGHT / 2:.1f}"/>'
    )
    return svg(WIDTH, HEIGHT, body, css, word)


def main() -> int:
    out_dir = ROOT / "assets"
    out_dir.mkdir(exist_ok=True)
    for word in HEADINGS:
        path = out_dir / f"hd-{word}.svg"
        path.write_text(build(word))
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
