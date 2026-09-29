#!/usr/bin/env python3
"""Build the Grand Central system map and write it into index.html.

Edit STATIONS and LINES below, then run from the repo root:
    python3 tools/build_map.py

The SVG is written between the <!-- MAP:START --> and <!-- MAP:END -->
markers in index.html. Coordinates run roughly x 40–1340, y 82–918 (see VIEW).

Station fields
  name    label text; use "\n" for a line break
  href    link target (omit for planned stops)
  x, y    position on the canvas
  label   where the label sits: above, below, left, right, above-right
  kind    stop | hub (first station of a line) | xfer (shared by two lines) | gc
  status  live | building | planned
  note    small mono caption under the name (optional)
  ret     True if that page links back to www.tahreemkarim.xyz (draws ⇄)
  line    which line colors the dot and ⇄
"""
from html import escape
from pathlib import Path

G = "https://garden.tahreemkarim.xyz"
R = "https://risingtigers.tahreemkarim.xyz"
P = "https://github.com/TahreemK13/portfolio"

STATIONS = {
    # Grand Central: every line starts here
    "gc": dict(name="Grand Central", href="/", x=200, y=400, label="left",
               kind="gc", note="You are here", line="home"),

    # Shared trunk — Now, Science and Resources sit in the nav of every
    # home, garden and portfolio page, so all three lines run through them.
    "now":  dict(name="Now", href="/now", x=290, y=400, label="below", kind="xfer", ret=True,
                 note="Updated Mar 2026", line="home"),
    "sci":  dict(name="Science & CV", href="/science", x=380, y=400, label="above", kind="xfer", ret=True, line="home"),
    "free": dict(name="Free resources", href="/free-resources", x=470, y=400, label="below", kind="xfer", ret=True,
                 status="building", note="PDFs not linked yet", line="home"),

    # Home line spur — only reachable from tahreemkarim.xyz pages
    "art":  dict(name="Art", href="/art", x=650, y=400, label="below", ret=True, status="building", note="Coming soon", line="home"),
    "trav": dict(name="Travel", href="/travel", x=760, y=400, label="below", ret=True, status="building", note="Coming soon", line="home"),

    # Garden line — garden.tahreemkarim.xyz
    "gdn":  dict(name="Digital garden", href=G, x=650, y=160, label="above", kind="hub", ret=True, line="garden"),
    "lib":  dict(name="Library", href=f"{G}/library", x=746, y=160, label="below", ret=True,
                 note="Also on portfolio", line="garden"),
    "cur":  dict(name="Online curriculum", href=f"{G}/posts/on_curriculum.html", x=842, y=160, label="above", ret=True, line="garden"),
    "born": dict(name="Born with it?", href=f"{G}/posts/on-philosophy.html", x=938, y=160, label="below", ret=True, line="garden"),
    "mvd":  dict(name="Marvel vs. DC", href=f"{G}/posts/comics-multimodal.html", x=1034, y=160, label="above", ret=True,
                 note="ML seedling", line="garden"),
    "brain": dict(name="Brainstorm with us?", href=f"{G}/posts/rti_brainstorm.html", x=1130, y=160, label="above-right",
                  kind="xfer", ret=True, note="Garden ⇆ Rising Tigers", line="garden"),
    "scicomm": dict(name="SciComm as design", x=1240, y=160, label="below", status="planned", note="Planned", line="garden"),

    # Portfolio line — portfolio.tahreemkarim.xyz (one page; stops are what it links to)
    "pf":   dict(name="Portfolio", href="https://portfolio.tahreemkarim.xyz", x=650, y=600, label="below",
                 kind="hub", ret=True, note="Resume PDF", line="portfolio"),
    "age":  dict(name="Aging biomarkers", href=f"{P}/blob/main/Visualizations", x=730, y=600, label="above",
                 note="Brown University", line="portfolio"),
    "shm":  dict(name="SHM simulator", href=f"{P}/blob/main/Coding/SHM%20simulator%20Prototype_ntbk.ipynb",
                 x=810, y=600, label="below", note="Notebook", line="portfolio"),
    "sbh":  dict(name="SynBioHub parts", href="https://tahreemk13.github.io/SynBioHub_parts_visualization/",
                 x=890, y=600, label="above", note="Interactive", line="portfolio"),
    "m593": dict(name="SIADS 593\nMilestone I", href="https://github.com/KCYL/SIADS593-milestone1-project",
                 x=970, y=600, label="below", note="Team repo", line="portfolio"),
    "pres": dict(name="Presentations", href=f"{P}/tree/main/Presentations", x=1050, y=600, label="above",
                 note="4 decks", line="portfolio"),
    "mmm":  dict(name="Math, Murder, and\nMaking a Difference", href=f"{R}/activism/", x=1130, y=600, label="right",
                 kind="xfer", ret=True, note="Portfolio ⇆ Rising Tigers", line="tigers"),

    # Rising Tigers line — risingtigers.tahreemkarim.xyz. Entered from the garden
    # (Brainstorm) or the portfolio (the article); no trunk page links here.
    "rti":  dict(name="Rising Tigers", href=R, x=1130, y=240, label="right", kind="hub",
                 note="Guides · causes", line="tigers"),
    "congo": dict(name="Congo", href=f"{R}/artifacts/congo/", x=1130, y=330, label="right", note="+ PDF", line="tigers"),
    "sudan": dict(name="Sudan", href=f"{R}/artifacts/sudan/", x=1130, y=420, label="right", note="+ PDF", line="tigers"),
    "pal":  dict(name="Palestine", href=f"{R}/artifacts/palestine/", x=1130, y=510, label="right", note="+ PDF", line="tigers"),
    "srcl": dict(name="Source library", href="https://github.com/TahreemK13/Rising_Tigers_Initiative/tree/main/library",
                 x=1130, y=670, label="right", note="GitHub", line="tigers"),
    "arti": dict(name="Artifacts index", href=f"{R}/artifacts/", x=1130, y=740, label="right", status="building",
                 note="Unlinked", line="tigers"),
    "bang": dict(name="Bangladesh", x=1130, y=800, label="right", status="planned", note="Planned", line="tigers"),
    "arm":  dict(name="Armenia", x=1130, y=860, label="right", status="planned", note="Planned", line="tigers"),

    # Profiles — elsewhere on the internet
    "gh":   dict(name="GitHub", href="https://github.com/TahreemK13", x=200, y=470, label="left", line="profiles"),
    "li":   dict(name="LinkedIn", href="https://www.linkedin.com/in/tahreem-karim/", x=200, y=520, label="left", line="profiles"),
    "cv":   dict(name="CV", href="https://drive.google.com/file/d/1RAJkQ8-j90F0jiusWNYQVpaJC3LeLOdm/view?usp=sharing",
                 x=200, y=570, label="left", line="profiles"),
    "fl":   dict(name="Flickr", href="https://www.flickr.com/photos/tahreemkphotography/", x=200, y=620, label="left", line="profiles"),
    "ig":   dict(name="Instagram", href="https://www.instagram.com/tahreemkphoto/", x=200, y=670, label="left", line="profiles"),
    "raja": dict(name="Raja", href="https://www.instagram.com/raja.hobbes.tigerdog/", x=200, y=720, label="left", line="profiles"),
    "rli":  dict(name="RTI LinkedIn", href="https://www.linkedin.com/company/rising-tigers-initiative/", x=200, y=770,
                 label="left", line="profiles"),
    "rig":  dict(name="RTI Instagram", href="https://www.instagram.com/the_rising_tigers_initiative/", x=200, y=820,
                 label="left", line="profiles"),
}

# Each line: its track as polylines. "planned" segments draw dotted.
# A line's name tag is drawn at `tag` (x, y, anchor).
# Garden and Portfolio run parallel to Home (±10px) through the shared trunk,
# then split at x=570: Garden north, Portfolio south, Home straight on.
LINES = [
    dict(id="profiles", name="PROFILES", tag=(200, 862, "middle"),
         track=[[(200, 400), (200, 820)]]),
    dict(id="garden", name="GARDEN LINE", tag=(586, 300, "start"),
         track=[[(200, 390), (570, 390), (570, 200), (610, 160), (1130, 160)]],
         planned=[[(1130, 160), (1240, 160)]]),
    dict(id="portfolio", name="PORTFOLIO LINE", tag=(586, 500, "start"),
         track=[[(200, 410), (570, 410), (570, 560), (610, 600), (1130, 600)]]),
    dict(id="home", name="HOME LINE", tag=(784, 405, "start"),
         track=[[(200, 400), (760, 400)]]),
    dict(id="tigers", name="RISING TIGERS LINE", tag=(1130, 902, "middle"),
         track=[[(1130, 160), (1130, 740)]],
         planned=[[(1130, 740), (1130, 860)]]),
]

VIEW = (40, 82, 1300, 836)  # x, y, width, height of the visible canvas
BG = "#0a0212"


def pts(seq):
    return " ".join(f"{x},{y}" for x, y in seq)


def marker(s):
    x, y, line = s["x"], s["y"], s["line"]
    kind, status = s.get("kind", "stop"), s.get("status", "live")
    if kind == "gc":
        return (f'<circle cx="{x}" cy="{y}" r="26" fill="none" stroke="var(--link)" stroke-opacity=".3" stroke-width="2"/>'
                f'<circle cx="{x}" cy="{y}" r="17" fill="var(--fg)" stroke="{BG}" stroke-width="4"/>')
    if status == "planned":
        return f'<circle cx="{x}" cy="{y}" r="7" fill="{BG}" stroke="var(--muted)" stroke-width="2" stroke-dasharray="1.5 3.5"/>'
    if status == "building":
        return f'<circle cx="{x}" cy="{y}" r="7.5" fill="{BG}" stroke="var(--orange)" stroke-width="2.5" stroke-dasharray="3 3"/>'
    if kind == "xfer":
        return (f'<circle cx="{x}" cy="{y}" r="12" fill="var(--fg)" stroke="{BG}" stroke-width="4"/>'
                f'<circle cx="{x}" cy="{y}" r="14" fill="none" stroke="var(--fg)" stroke-width="1.5"/>')
    if kind == "hub":
        return f'<circle cx="{x}" cy="{y}" r="10" fill="var(--fg)" stroke="var(--line-{line})" stroke-width="4"/>'
    return f'<circle cx="{x}" cy="{y}" r="7.5" class="t-{line}" stroke="{BG}" stroke-width="3"/>'


def label(s):
    x, y, pos = s["x"], s["y"], s["label"]
    lines = s["name"].split("\n")
    big = s.get("kind") == "gc"
    off = 30 if big else 20
    ret = f'<tspan class="t-{s["line"]}"> ⇄</tspan>' if s.get("ret") else ""
    note = s.get("note")
    lh = 18
    if pos == "below":
        ax, anchor, ys = x, "middle", [y + 32 + i * lh for i in range(len(lines))]
        ny = ys[-1] + 16
    elif pos == "above":
        ax, anchor = x, "middle"
        base = y - 22 - (16 if note else 0)
        ys = [base - (len(lines) - 1 - i) * lh for i in range(len(lines))]
        ny = y - 20
    elif pos == "above-right":
        ax, anchor = x + 18, "start"
        base = y - 24 - (16 if note else 0)
        ys = [base - (len(lines) - 1 - i) * lh for i in range(len(lines))]
        ny = y - 22
    else:  # left / right
        ax = x + off if pos == "right" else x - off
        anchor = "start" if pos == "right" else "end"
        top = y + 5 - (len(lines) - 1) * lh / 2 - (8 if note else 0)
        ys = [top + i * lh for i in range(len(lines))]
        ny = ys[-1] + 16
    cls = "st-gc" if big else "st-name"
    out = []
    for i, (t, ty) in enumerate(zip(lines, ys)):
        tail = ret if i == len(lines) - 1 else ""
        out.append(f'<text x="{ax}" y="{ty:g}" text-anchor="{anchor}" class="{cls}">{escape(t)}{tail}</text>')
    if note:
        out.append(f'<text x="{ax}" y="{ny:g}" text-anchor="{anchor}" class="st-note">{escape(note)}</text>')
    return "".join(out)


def station(key, s):
    status = s.get("status", "live")
    full = s["name"].replace("\n", " ")
    desc = {"building": ", under construction", "planned": ", planned"}.get(status, "")
    body = marker(s) + label(s)
    if s.get("href") and status != "planned":
        return (f'<a href="{escape(s["href"])}" aria-label="{escape(full + desc)}">'
                f'<title>{escape(full + desc)}</title>{body}</a>')
    return f'<g class="st-planned" role="img" aria-label="{escape(full + desc)}">{body}</g>'


def build():
    parts = [f'<svg class="net" viewBox="{" ".join(map(str, VIEW))}" xmlns="http://www.w3.org/2000/svg" '
             f'aria-labelledby="net-title"><title id="net-title">Connected map of Tahreem Karim\'s websites</title>']
    parts.append("<g aria-hidden=\"true\">")
    for ln in LINES:
        for seg in ln["track"]:
            parts.append(f'<polyline class="net-line l-{ln["id"]}" points="{pts(seg)}"/>')
        for seg in ln.get("planned", []):
            parts.append(f'<polyline class="net-line planned l-{ln["id"]}" points="{pts(seg)}"/>')
    for ln in LINES:
        tx, ty, anchor = ln["tag"]
        parts.append(f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" class="st-tag t-{ln["id"]}">{ln["name"]}</text>')
    parts.append("</g>")
    for key, s in STATIONS.items():
        parts.append(station(key, s))
    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    page = Path(__file__).resolve().parent.parent / "index.html"
    html = page.read_text(encoding="utf-8")
    start = html.index("<!-- MAP:START")
    start = html.index("-->", start) + 3
    end = html.index("<!-- MAP:END -->")
    page.write_text(html[:start] + "\n" + build() + "\n" + html[end:], encoding="utf-8")
    print(f"Map written to {page} ({len(STATIONS)} stations, {len(LINES)} lines)")
