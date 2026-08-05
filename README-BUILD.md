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

    # section headings
    python3 scripts/generate_headings.py

    # the three header pieces, as they currently stand
    python3 scripts/generate_portrait.py "Green pfp (!.jpeg" \
        --crop 0.24,0.03,0.70,0.50 --flood 14 --blank 1 \
        --colour --cols 60 --width 270 --name face \
        --contrast 14 --band 0.28,0.86 --saturation 1.6

    python3 scripts/generate_portrait.py Knight_16.webp \
        --colour --cols 60 --width 270 --name knight

    python3 scripts/generate_portrait.py _.jpeg --blur 6 \
        --colour --cols 60 --width 270 --name eye

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

## colour, and why one file now covers both themes

In monochrome the portrait needed two files. Density is the encoding, and
density does not survive a colour swap: on a dark ground the lit side of the
face has to be the *dense* side or the face reads as a hole, and on a light
ground the ramp runs the other way.

With `--colour` that goes away. Each character takes its colour from the
matching cell of the source, so the drawing carries its own values and one
file serves both grounds.

Two things make per-character colour work here rather than turn to static:

* **Quantising** to ten colours. Flat artwork collapses into a few regions, so
  the result reads as the drawing instead of as noise — and long single-colour
  runs compress into one `<tspan>` each rather than one per character.
* **Remapping value, keeping hue.** A colour lifted straight off the source
  paints near-black glyphs on a near-black README. Hue and saturation are what
  make it read as *that* image, so they survive; value is forced into a narrow
  central band (0.40–0.72) that holds up on white and on #0d1117 alike.

The general warning still stands — per-character colour on a *photograph*
degenerates into static. It works here because all three sources are
flat-palette artwork.

## choosing a source image

Three were tried. What decided it:

* A halftone close-up rendered as an even field — the dot screen averages to
  one mid-tone at 90 columns, and there is nothing left to draw with.
* A 240px pixel-art sprite oversampled badly: each sprite pixel became about
  three characters, so every edge came out as a blocky triple. It would need
  roughly 40 columns, which is too small to lead a page.
* The manga portrait won: real tonal range, a face that survives cropping to
  fill the frame, and a light backdrop that `--blank 3` clears to empty page.

## the flags, and which source needs which

    --crop l,t,r,b   fractions of the frame; crop tight or the face gets no
                     characters to work with
    --flood TOL      drop the background by flooding in from the corners.
                     Needs a backdrop whose value differs from the subject
    --rembg          semantic segmentation instead, for when it does not
    --blur R         low-pass first. The fix for halftone or dithered art:
                     the dot screen aliases against the character grid
    --blank N        render the N faintest ramp levels as empty space
    --colour         per-character colour from the source
    --palette N      colours to quantise to (default 10)
    --invert         source is a dark subject on a light background
    --cols / --width grid columns, and rendered width in the README
    --contrast PCT   percentile clipped off each end before mapping to the
                     ramp. Higher clips harder, so more cells land on the
                     extremes and the tonal separation widens
    --band LO,HI     brightness band the sampled colours are remapped into.
                     Widen for punchier colour; too wide and the extremes
                     wash out on one ground or the other
    --saturation X   saturation multiplier on the sampled colours

`face` needs `--flood 14`, because the backdrop is a flat light green that a
corner flood separates cleanly. `knight` needs nothing — it ships its own alpha
channel, which is used directly. `eye` needs `--blur 6`, because it is a
halftone and the dots alias into an even grey field without it.

## do I have to run anything on a schedule?

No. The only thing that changes on its own is the stats, and
`.github/workflows/refresh-stats.yml` handles that — it runs every night at
05:17 UTC on GitHub's machines and commits only when a drawing actually
changed. Nothing to install, nothing to remember.

The header art is different: it is generated by hand and committed, because
the source images do not change unless you change them. Re-run
`generate_portrait.py` only when you want different pictures or different
settings.

To force a stats refresh without waiting for the schedule:

    gh workflow run refresh-stats.yml
