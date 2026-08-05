# how this profile builds itself

Nothing on the profile is fetched from a third-party service. Every graphic is
an SVG drawn by a script in `scripts/`, with the typeface inlined as base64 so
the file has no subresources to fetch.

## nightly

`.github/workflows/refresh-stats.yml` runs `scripts/generate_stats.py` on a
schedule and commits `assets/{stats,streak,langs,year}.svg` only when they
actually change. That generator is standard library only — `urllib` against the
GraphQL API — so there is no dependency in CI that can break.

## by hand

These outputs are committed and regenerated only when you want them to change:

    pip install fonttools brotli pillow numpy

    # subset the typeface (needed if you change any label text)
    python3 scripts/build_fonts.py path/to/JetBrainsMono-Regular.ttf

    # the wordmark
    python3 scripts/generate_hero.py path/to/JetBrainsMono-Regular.ttf

    # section headings
    python3 scripts/generate_headings.py

    # an ASCII portrait, if you have a photo that suits it
    python3 scripts/generate_portrait.py photo.jpg

## what GitHub allows

Tested by posting the README to `POST /markdown`, which applies the same
sanitiser as the site.

    STRIPPED   <style> blocks, style="", class="", inline <svg>, <font>
    KEPT       <sub> <sup> <kbd> <samp> <blockquote> <details> <hr> <picture>
               align="" and width="" on <img>

Consequences: README text cannot change font, so anything in JetBrains Mono has
to be an image; motion has to be SMIL inside the SVG, because scripts are
stripped; and CSS *inside* an SVG survives, because the sanitiser never parses
the image document.

Section headings are images, which costs the anchor links GitHub's outline
sidebar is built from. The `alt` text carries the word for screen readers.

## typeface

JetBrains Mono, SIL OFL 1.1 — see `fonts/OFL.txt`. It is 600/1000 units, which
is exactly the 0.600 em advance the character grid assumes, so the geometry
needs no correction. The font file ships in a public repo, so it has to be
OFL or similar; commercial fonts are not an option here.

Subsets are per role — 13 glyphs for the ramp, 92 for labels — because every
SVG carries its own copy.

## credit

The portrait pipeline follows the ASCII Portrait README Guide, and the overall
approach follows "A GitHub profile that generates itself".
