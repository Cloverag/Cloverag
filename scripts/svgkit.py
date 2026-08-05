"""Shared SVG plumbing. Standard library only — this is imported by the
generator the workflow runs, and a dependency here would be a dependency in CI.

Two things every graphic on the page needs: the inlined typeface, and the
theme colours. Both live here so the page can't drift out of one visual
language.
"""
import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"

# The portrait grid assumes an advance width of exactly 0.600 em. JetBrains
# Mono is 600/1000 units, so these two numbers stay locked together: change
# the size and CHAR_W must follow, or the grid shears.
FONT_SIZE = 12.9
CHAR_W = FONT_SIZE * 0.600  # 7.74
# Monospace cells are about twice as tall as wide; 0.48 is the ratio the row
# count is derived from, so the cell height is its reciprocal.
LINE_H = CHAR_W / 0.48  # 16.125

RAMP = " .`:-=+*cs#%@"

# Sampled from the avatar so the page and the profile picture agree.
THEME = {
    "dark": {
        "ink": "#e6edf3",
        "dim": "#8b949e",
        "faint": "#4d5560",
        "accent": "#f08796",
        "cool": "#7aa2f7",
        "rule": "#30363d",
    },
    "light": {
        "ink": "#1f2328",
        "dim": "#59636e",
        "faint": "#aeb7c0",
        "accent": "#c2445c",
        "cool": "#3b5bdb",
        "rule": "#d1d9e0",
    },
}

_font_cache: dict[str, str] = {}


def font_b64(name: str) -> str:
    """base64 of a subset woff2. An external font URL cannot work here: these
    SVGs load through an <img> tag and browsers refuse subresource fetches for
    image documents. A data URI is the only route that renders."""
    if name not in _font_cache:
        _font_cache[name] = base64.b64encode((FONTS / f"{name}.woff2").read_bytes()).decode()
    return _font_cache[name]


def family(name: str) -> str:
    """Each subset gets its own family. Two @font-face rules sharing a family
    name and carrying no unicode-range collapse to whichever came last, which
    would silently drop the ramp glyphs from any file that inlines both."""
    return f"JBM{name}"


def font_face(name: str) -> str:
    return (
        f"@font-face{{font-family:'{family(name)}';font-style:normal;font-weight:400;"
        f"src:url(data:font/woff2;base64,{font_b64(name)}) format('woff2');}}"
    )


def paint(css: str, mode: str) -> str:
    """Substitute var(--role) for the literal hex of one theme.

    Custom properties would be tidier, but a renderer that doesn't resolve
    var() paints every one of them black rather than falling back to something
    readable. Literal colours plus a media-query override degrade to the light
    theme instead, which is the failure everyone can live with.
    """
    for role, hex_ in THEME[mode].items():
        css = css.replace(f"var(--{role})", hex_)
    return css


def themed(css: str) -> str:
    """Light rules, then the same rules again under prefers-color-scheme:dark.

    The <style> inside an SVG survives — GitHub's sanitiser strips style out of
    the *markdown*, not out of an image document it never parses. Equal
    specificity, so the later block wins when it matches.
    """
    return (paint(css, "light")
            + "@media(prefers-color-scheme:dark){" + paint(css, "dark") + "}")


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def svg(width: float, height: float, body: str, css: str, title: str,
        fonts: tuple[str, ...] = ("ui",),
        display_width: float | None = None,
        theme_switch: bool = True) -> str:
    """Wrap a body in a root <svg>. width/height are the coordinate system;
    display_width is what the README renders it at.

    `fonts` are emitted once, outside the theme duplication — a base64 face
    repeated inside the dark block would double the file for nothing.

    `theme_switch=False` emits the CSS verbatim, for files that are already
    committed to one theme. An ASCII portrait cannot switch on colour alone:
    density is the encoding, so a light-on-dark and a dark-on-light rendering
    need opposite ramps and therefore separate files behind a <picture>.
    """
    dw = f' width="{display_width:.0f}"' if display_width else ""
    faces = "".join(font_face(f) for f in fonts)
    style = themed(css) if theme_switch else paint(css, "light")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}"'
        f'{dw} role="img" aria-label="{esc(title)}">'
        f"<title>{esc(title)}</title>"
        f"<style>{faces}{style}</style>"
        f"{body}</svg>"
    )


def typed_rows(rows: list[str], x: float, y0: float, cls: str = "r",
               stagger: float = 0.09, dur: float = 0.55,
               cursor: bool = True) -> str:
    """Rows that type themselves in.

    Each row lives in a clipPath whose rect animates width 0 -> full, with a
    small block riding the wipe edge as a cursor. Scripts are stripped from
    anything GitHub renders, so the motion has to be SMIL inside the file —
    which GitHub does run. fill="freeze" everywhere: the page prints once and
    stops. Nothing loops.
    """
    out = []
    defs = []
    for i, row in enumerate(rows):
        w = len(row) * CHAR_W
        begin = i * stagger
        # The authored width is the FINAL width, not 0, and the animation runs
        # from 0 to it. Authoring 0 would mean any renderer that doesn't run
        # SMIL — a cache, a scraper, an email client, a Blink clip-path
        # invalidation bug — shows a blank rectangle where the name should be.
        # This way the worst case is "it didn't animate", not "it isn't there".
        defs.append(
            f'<clipPath id="c{i}"><rect x="{x:.2f}" y="{y0 + i * LINE_H - LINE_H:.2f}" '
            f'height="{LINE_H * 1.6:.2f}" width="{w:.2f}">'
            f'<animate attributeName="width" from="0" to="{w:.2f}" '
            f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/></rect></clipPath>'
        )
    out.append("<defs>" + "".join(defs) + "</defs>")
    for i, row in enumerate(rows):
        y = y0 + i * LINE_H
        out.append(
            f'<text class="{cls}" x="{x:.2f}" y="{y:.2f}" clip-path="url(#c{i})" '
            f'xml:space="preserve">{esc(row)}</text>'
        )
        if cursor and row.strip():
            w = len(row) * CHAR_W
            begin = i * stagger
            out.append(
                f'<rect class="cur" x="{x:.2f}" y="{y - LINE_H * 0.72:.2f}" '
                f'width="{CHAR_W:.2f}" height="{LINE_H * 0.8:.2f}" opacity="0">'
                f'<animate attributeName="x" from="{x:.2f}" to="{x + w:.2f}" '
                f'dur="{dur:.2f}s" begin="{begin:.2f}s" fill="freeze"/>'
                f'<set attributeName="opacity" to="1" begin="{begin:.2f}s"/>'
                f'<set attributeName="opacity" to="0" begin="{begin + dur:.2f}s"/>'
                f"</rect>"
            )
    return "".join(out)
