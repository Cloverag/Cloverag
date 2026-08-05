"""Draw four stat graphics from the GitHub GraphQL API.

Standard library only — urllib for the API, no dependencies to break in CI.

Run by .github/workflows/refresh-stats.yml on a schedule. Two determinism
rules are load-bearing; miss either and this commits a meaningless diff every
single night:

  1. The contribution window is pinned to whole UTC days. Left alone,
     contributionsCollection measures "the past year" from the moment of the
     request, so two runs minutes apart bucket days into different weeks and
     shift the sparkline by a fraction of a pixel.

  2. Repositories are filtered to privacy: PUBLIC. A personal token sees
     private repos and the workflow's token does not, so without this the
     language percentages disagree depending on who ran the script.
"""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from svgkit import CHAR_W, LINE_H, RAMP, ROOT, esc, svg  # noqa: E402

API = "https://api.github.com/graphql"
WIDTH = 840.0

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!, $cursor:String) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first:100, after:$cursor, ownerAffiliations:OWNER,
                 privacy:PUBLIC, isFork:false,
                 orderBy:{field:PUSHED_AT, direction:DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        stargazerCount
        languages(first:12, orderBy:{field:SIZE, direction:DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------- api

def call(token: str, variables: dict) -> dict:
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-selfbuild",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def fetch(login: str, token: str) -> tuple[dict, list[dict]]:
    today = datetime.now(timezone.utc).date()
    frm = datetime.combine(today - timedelta(days=364), datetime.min.time(),
                           tzinfo=timezone.utc)
    to = datetime.combine(today, datetime.max.time().replace(microsecond=0),
                          tzinfo=timezone.utc)

    variables = {
        "login": login,
        "from": frm.isoformat().replace("+00:00", "Z"),
        "to": to.isoformat().replace("+00:00", "Z"),
        "cursor": None,
    }
    data = call(token, variables)
    calendar = data["user"]["contributionsCollection"]["contributionCalendar"]

    repos = []
    page = data["user"]["repositories"]
    while True:
        repos.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        variables["cursor"] = page["pageInfo"]["endCursor"]
        page = call(token, variables)["user"]["repositories"]
    return calendar, repos


# ---------------------------------------------------------------- derive

def days(calendar: dict) -> list[tuple[date, int]]:
    out = []
    for week in calendar["weeks"]:
        for d in week["contributionDays"]:
            out.append((date.fromisoformat(d["date"]), d["contributionCount"]))
    out.sort()
    return out


def streaks(series: list[tuple[date, int]]) -> dict:
    """Current and longest run of consecutive contributing days.

    Today is excluded from breaking the current streak: the day is still in
    progress, and a profile that reports a broken streak every morning until
    the first push is just wrong.
    """
    today = datetime.now(timezone.utc).date()
    best = best_span = None
    run = run_start = None
    for d, n in series:
        if n > 0:
            run_start = d if run is None else run_start
            run = 1 if run is None else run + 1
            if best is None or run > best:
                best, best_span = run, (run_start, d)
        else:
            run = run_start = None

    cur = 0
    cur_span = None
    for d, n in reversed(series):
        if n == 0:
            if d == today:
                continue  # still in progress
            break
        cur += 1
        cur_span = (d, cur_span[1] if cur_span else d)
    return {
        "current": cur,
        "current_span": cur_span,
        "longest": best or 0,
        "longest_span": best_span,
    }


def languages(repos: list[dict], top: int = 6):
    """Top languages, with the *full* totals alongside them.

    The totals have to come from every language, not from the truncated top
    slice — dividing by the slice would inflate every bar to make six entries
    add up to 100%.
    """
    by_bytes: dict[str, int] = {}
    by_repo: dict[str, int] = {}
    for repo in repos:
        edges = repo["languages"]["edges"]
        for e in edges:
            by_bytes[e["node"]["name"]] = by_bytes.get(e["node"]["name"], 0) + e["size"]
        if edges:
            primary = edges[0]["node"]["name"]
            by_repo[primary] = by_repo.get(primary, 0) + 1
    rank_b = sorted(by_bytes.items(), key=lambda kv: (-kv[1], kv[0]))
    rank_r = sorted(by_repo.items(), key=lambda kv: (-kv[1], kv[0]))
    return (rank_b[:top], sum(by_bytes.values()),
            rank_r[:top], sum(by_repo.values()))


def fmt(d: date) -> str:
    return d.strftime("%d %b %Y").lstrip("0")


# GitHub's own names for these are too long for the label column, and a
# mid-word truncation ("Jupyter Not") reads as a bug rather than a shortening.
ALIASES = {"Jupyter Notebook": "Jupyter", "Objective-C": "Obj-C"}


def label_of(name: str, width: int = 13) -> str:
    name = ALIASES.get(name, name)
    return name if len(name) <= width else name[:width - 1] + "…"


# ---------------------------------------------------------------- draw

BASE_CSS = (
    ".lbl{font-family:'JBMui',monospace;font-size:11px;fill:var(--dim);"
    "letter-spacing:1.4px;}"
    ".val{font-family:'JBMui',monospace;font-size:13px;fill:var(--ink);}"
    ".huge{font-family:'JBMui',monospace;font-size:46px;fill:var(--ink);}"
    ".big{font-family:'JBMui',monospace;font-size:30px;fill:var(--ink);}"
    ".rule{stroke:var(--rule);stroke-width:1;}"
)


def stats_svg(series, calendar) -> str:
    """Hero total plus a weekly sparkline.

    Weekly, not daily. A line through daily counts claims values that never
    existed — 0, 0, 11, 0 is not a slope. Aggregated to weeks, continuity is
    defensible and an area chart is honest.
    """
    total = calendar["totalContributions"]
    weeks = [sum(n for _, n in series[i:i + 7]) for i in range(0, len(series), 7)]
    peak = max(weeks) or 1

    h = 176.0
    pad_l, pad_r = 24.0, 24.0
    chart_x = 400.0
    chart_w = WIDTH - chart_x - pad_r
    chart_y, chart_h = 62.0, 78.0
    step = chart_w / max(len(weeks) - 1, 1)

    pts = [(chart_x + i * step, chart_y + chart_h - (v / peak) * chart_h)
           for i, v in enumerate(weeks)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = (f"{pts[0][0]:.1f},{chart_y + chart_h:.1f} " + line
            + f" {pts[-1][0]:.1f},{chart_y + chart_h:.1f}")

    active = sum(1 for _, n in series if n > 0)
    busiest = max(series, key=lambda kv: kv[1])

    css = (
        BASE_CSS
        + ".spark{fill:none;stroke:var(--accent);stroke-width:1.6;"
          "stroke-linejoin:round;}"
        + ".sparkfill{fill:var(--accent);opacity:.15;}"
        + ".base{stroke:var(--rule);stroke-width:1;}"
    )
    body = (
        f'<text class="lbl" x="{pad_l}" y="34">contributions · last 365 days</text>'
        f'<text class="huge" x="{pad_l}" y="96">{total:,}</text>'
        f'<text class="lbl" x="{pad_l}" y="126">{active} active days</text>'
        f'<text class="lbl" x="{pad_l}" y="146">peak {busiest[1]} on '
        f'{esc(fmt(busiest[0]))}</text>'
        f'<text class="lbl" x="{chart_x:.0f}" y="34">by week · peak {peak}</text>'
        f'<polygon class="sparkfill" points="{area}"/>'
        f'<polyline class="spark" points="{line}"/>'
        f'<line class="base" x1="{chart_x:.0f}" y1="{chart_y + chart_h:.1f}" '
        f'x2="{WIDTH - pad_r}" y2="{chart_y + chart_h:.1f}"/>'
        f'<text class="lbl" x="{chart_x:.0f}" y="{chart_y + chart_h + 20:.1f}">'
        f'52 weeks ago</text>'
        f'<text class="lbl" x="{WIDTH - pad_r}" y="{chart_y + chart_h + 20:.1f}" '
        f'text-anchor="end">now</text>'
    )
    return svg(WIDTH, h, body, css,
               f"{total} contributions in the last 365 days, {active} active days")


def streak_svg(s: dict) -> str:
    h = 128.0
    css = BASE_CSS
    cells = [
        ("current streak", s["current"], s["current_span"]),
        ("longest streak", s["longest"], s["longest_span"]),
    ]
    body = [f'<line class="rule" x1="{WIDTH / 2:.0f}" y1="26" '
            f'x2="{WIDTH / 2:.0f}" y2="{h - 22:.0f}"/>']
    for i, (label, n, span) in enumerate(cells):
        x = 24.0 + i * (WIDTH / 2)
        rng = f"{fmt(span[0])} — {fmt(span[1])}" if span and n else "no run yet"
        unit = "day" if n == 1 else "days"
        body.append(
            f'<text class="lbl" x="{x:.0f}" y="34">{label}</text>'
            f'<text class="big" x="{x:.0f}" y="78">{n}'
            f'<tspan class="lbl" dx="8">{unit}</tspan></text>'
            f'<text class="lbl" x="{x:.0f}" y="102">{esc(rng)}</text>'
        )
    return svg(WIDTH, h, "".join(body), css,
               f"current streak {s['current']} days, longest {s['longest']} days")


def langs_svg(by_bytes, total_b, by_repo, total_r) -> str:
    rows = max(len(by_bytes), len(by_repo))
    h = 62.0 + rows * 26.0
    total_b = total_b or 1
    total_r = total_r or 1
    col_w = WIDTH / 2 - 40

    css = (
        BASE_CSS
        + ".track{fill:var(--rule);}"
        + ".barA{fill:var(--accent);}"
        + ".barB{fill:var(--cool);}"
        + ".pct{font-family:'JBMui',monospace;font-size:11px;fill:var(--dim);}"
        + ".name{font-family:'JBM',monospace;font-size:12px;fill:var(--ink);}"
    )
    body = [
        '<text class="lbl" x="24" y="30">by bytes written</text>',
        f'<text class="lbl" x="{WIDTH / 2 + 16:.0f}" y="30">by repositories</text>',
    ]
    for col, (data, total, cls) in enumerate(
            ((by_bytes, total_b, "barA"), (by_repo, total_r, "barB"))):
        x0 = 24.0 + col * (WIDTH / 2 - 8)
        for i, (name, val) in enumerate(data):
            y = 56.0 + i * 26.0
            frac = val / total
            bar_x = x0 + 116
            bar_w = col_w - 170
            body.append(
                f'<text class="name" x="{x0:.0f}" y="{y + 9:.0f}">'
                f'{esc(label_of(name))}</text>'
                f'<rect class="track" x="{bar_x:.0f}" y="{y:.0f}" '
                f'width="{bar_w:.0f}" height="8" rx="4"/>'
                f'<rect class="{cls}" x="{bar_x:.0f}" y="{y:.0f}" '
                f'width="{max(bar_w * frac, 2):.1f}" height="8" rx="4"/>'
                f'<text class="pct" x="{bar_x + bar_w + 10:.0f}" y="{y + 8:.0f}">'
                f'{frac * 100:.1f}%</text>'
            )
    top = by_bytes[0][0] if by_bytes else "nothing yet"
    return svg(WIDTH, h, "".join(body), css, f"top languages, led by {top}")


def year_svg(series) -> str:
    """The year at one character per day, in the portrait's own ramp.

    Density is the encoding, so this needs no colour scale and no legend
    beyond the ramp itself.
    """
    peak = max((n for _, n in series), default=0) or 1
    # 53 columns of 7 days, laid out the way the calendar reads.
    first = series[0][0]
    lead = (first.weekday() + 1) % 7  # GitHub weeks start Sunday
    cells = [None] * lead + [n for _, n in series]
    cols = (len(cells) + 6) // 7
    grid = [[" "] * cols for _ in range(7)]
    for i, n in enumerate(cells):
        if n is None:
            continue
        col, row = divmod(i, 7)
        if col < cols:
            # Non-zero days always get at least the first visible glyph, so a
            # quiet day is distinguishable from no day at all.
            idx = 0 if n == 0 else max(1, round((n / peak) ** 0.55 * (len(RAMP) - 1)))
            grid[row][col] = RAMP[idx]

    grid_w = cols * CHAR_W
    top = 52.0
    h = top + 7 * LINE_H + 34.0
    css = (
        f".d{{font-family:'JBMramp',monospace;font-size:12.9px;fill:var(--accent);"
          "white-space:pre;}"
        + ".lbl{font-family:'JBMui',monospace;font-size:11px;fill:var(--dim);"
          "letter-spacing:1.4px;}"
        + ".ramp{font-family:'JBMramp',monospace;font-size:12.9px;fill:var(--faint);"
          "white-space:pre;}"
    )
    x0 = 24.0
    body = [
        f'<text class="lbl" x="{x0:.0f}" y="30">one character per day '
        f'· {fmt(series[0][0])} to {fmt(series[-1][0])}</text>'
    ]
    for r, row in enumerate(grid):
        body.append(
            f'<text class="d" x="{x0:.0f}" y="{top + r * LINE_H:.1f}" '
            f'xml:space="preserve">{esc("".join(row))}</text>'
        )
    legend_y = top + 7 * LINE_H + 16
    body.append(
        f'<text class="lbl" x="{x0:.0f}" y="{legend_y:.0f}">quiet</text>'
        f'<text class="ramp" x="{x0 + 46:.0f}" y="{legend_y:.0f}" '
        f'xml:space="preserve">{esc(RAMP[1:])}</text>'
        f'<text class="lbl" x="{x0 + 46 + len(RAMP) * CHAR_W:.0f}" '
        f'y="{legend_y:.0f}">busy · peak {peak}</text>'
    )
    return svg(max(grid_w + 48, 480), h, "".join(body), css,
               title=f"daily contribution calendar, peak {peak} in one day",
               fonts=("ramp", "ui"))


# ---------------------------------------------------------------- main

def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")
    if not token or not login:
        print("GITHUB_TOKEN and GH_LOGIN must be set")
        return 1

    calendar, repos = fetch(login, token)
    series = days(calendar)
    by_bytes, total_b, by_repo, total_r = languages(repos)

    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    written = {
        "stats.svg": stats_svg(series, calendar),
        "streak.svg": streak_svg(streaks(series)),
        "langs.svg": langs_svg(by_bytes, total_b, by_repo, total_r),
        "year.svg": year_svg(series),
    }
    for name, content in written.items():
        (out / name).write_text(content)
        print(f"assets/{name}  {len(content) / 1024:.1f} KB")
    print(f"{calendar['totalContributions']} contributions · {len(repos)} public repos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
