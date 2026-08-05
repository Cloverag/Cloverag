"""Subset JetBrains Mono per role and write the woff2 files the SVGs inline.

Run this by hand, not in CI — it needs fonttools + brotli, and the output is
committed. The generators only read the .woff2 files and base64 them, which
keeps CI on the standard library.

    pip install fonttools brotli
    python3 scripts/build_fonts.py path/to/JetBrainsMono-Regular.ttf
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "fonts"

# One subset per role. The portrait only ever draws 13 glyphs, so shipping it
# the full alphabet would multiply the page weight for nothing.
SUBSETS = {
    "ramp": " .`:-=+*cs#%@",
    "ui": (
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789"
        " .,:;'\"/()[]{}+-=*#%&@_·—–…<>|"
    ),
}


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"no such font: {src}")
        return 1

    FONTS.mkdir(exist_ok=True)
    for name, chars in SUBSETS.items():
        out = FONTS / f"{name}.woff2"
        subprocess.run(
            [
                "pyftsubset",
                str(src),
                f"--text={chars}",
                "--flavor=woff2",
                "--layout-features=",
                "--no-hinting",
                "--desubroutinize",
                f"--output-file={out}",
            ],
            check=True,
        )
        print(f"{out.name:12} {out.stat().st_size / 1024:6.1f} KB  ({len(chars)} glyphs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
