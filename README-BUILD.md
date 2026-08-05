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

    # the portrait, as it currently stands
    python3 scripts/generate_portrait.py "Green pfp (!.jpeg" \
        --crop 0.24,0.03,0.70,0.50 --invert --blank 3

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

## the GITHUB_TOKEN caveat

The built-in `GITHUB_TOKEN` does not return the same contribution total as a
personal token. On this account a personal token reports 411 and the workflow
token reports 46; the gap is private-repo activity.

46 is what `github.com/users/<login>/contributions` serves to an anonymous
visitor, so it is the figure that matches what a reader can independently
check. Every label says "public" for that reason. Supplying a personal access
token instead would show the larger number at the cost of publishing a count
nobody else can verify.

## why the portrait is two files

Density is the encoding in ASCII art, and density does not survive a colour
swap. On a dark page the ink is light, so the lit side of the face has to be
the *dense* side or the face reads as a hole. On a light page the ink is dark
and the ramp has to run the other way.

So `generate_portrait.py` writes `portrait-light.svg` and `portrait-dark.svg`
with opposite ramps and fixed fills, and the README picks between them with
`<picture>` + `media="(prefers-color-scheme: dark)"` — both of which survive
the sanitiser, verified against `POST /markdown`.

`--invert` describes the *source*: a dark subject on a light background, which
is what an ink drawing or a manga panel is. The dark variant flips it.

## choosing a source image

Three were tried. What decided it:

* A halftone close-up rendered as an even field — the dot screen averages to
  one mid-tone at 90 columns, and there is nothing left to draw with.
* A 240px pixel-art sprite oversampled badly: each sprite pixel became about
  three characters, so every edge came out as a blocky triple. It would need
  roughly 40 columns, which is too small to lead a page.
* The manga portrait won: real tonal range, a face that survives cropping to
  fill the frame, and a light backdrop that `--blank 3` clears to empty page.
