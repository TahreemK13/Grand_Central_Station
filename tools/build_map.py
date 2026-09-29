#!/usr/bin/env python3
"""Build the Grand Central system map and write it into index.html.

Edit STATIONS and LINES below, then run from the repo root:
    python3 tools/build_map.py

The SVG is written between the <!-- MAP:START --> and <!-- MAP:END -->
markers in index.html. Coordinates run roughly x 40–1250, y 82–882 (see VIEW).

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
    "gc": dict(name="Grand Central", href="/", x=240, y=350, label="left",
               kind="gc", note="You are here", line="home"),

    # Home line — tahreemkarim.xyz
    "now":  dict(name="Now", href="/now", x=380, y=350, label="below", ret=True, note="Updated Mar 2026", line="home"),
    "sci":  dict(name="Science & CV", href="/science", x=510, y=350, label="below", ret=True, line="home"),
    "free": dict(name="Free resources", href="/free-resources", x=640, y=350, label="below", ret=True,
                 status="building", note="Downloads being linked", line="home"),
    "art":  dict(name="Art", href="/art", x=770, y=350, label="below", ret=True, status="building", note="Coming soon", line="home"),
    "trav": dict(name="Travel", href="/travel", x=900, y=350, label="below", ret=True, status="building", note="Coming soon", line="home"),

    # Garden line — garden.tahreemkarim.xyz
    "gdn":  dict(name="Digital garden", href=G, x=380, y=150, label="above", kind="hub", ret=True, line="garden"),
    "lib":  dict(name="Library", href=f"{G}/library", x=500, y=150, label="below", ret=True, line="garden"),
    "cur":  dict(name="Online curriculum", href=f"{G}/posts/on_curriculum.html", x=620, y=150, label="above", ret=True, line="garden"),
    "born": dict(name="Born with it?", href=f"{G}/posts/on-philosophy.html", x=740, y=150, label="below", ret=True, line="garden"),
    "mvd":  dict(name="Marvel vs. DC", href=f"{G}/posts/comics-multimodal.html", x=860, y=150, label="above", ret=True,
                 note="ML seedling", line="garden"),
    "brain": dict(name="Brainstorm with us?", href=f"{G}/posts/rti_brainstorm.html", x=1020, y=150, label="above-right",
                  kind="xfer", ret=True, note="Garden ⇆ Rising Tigers", line="garden"),
    "scicomm": dict(name="SciComm as design", x=1150, y=150, label="below", status="planned", note="Planned", line="garden"),

    # Portfolio line — portfolio.tahreemkarim.xyz
    "pf":   dict(name="Portfolio", href="https://portfolio.tahreemkarim.xyz", x=460, y=530, label="below",
                 kind="hub", ret=True, line="portfolio"),
    "sbh":  dict(name="SynBioHub parts", href="https://tahreemk13.github.io/SynBioHub_parts_visualization/",
                 x=575, y=530, label="above", note="Interactive", line="portfolio"),
    "age":  dict(name="Aging biomarkers", href=f"{P}/blob/main/Visualizations", x=690, y=530, label="below",
                 note="Brown University", line="portfolio"),
    "shm":  dict(name="SHM simulator", href=f"{P}/blob/main/Coding/SHM%20simulator%20Prototype_ntbk.ipynb",
                 x=805, y=530, label="above", note="Notebook", line="portfolio"),
    "pres": dict(name="Presentations", href=f"{P}/tree/main/Presentations", x=920, y=530, label="below",
                 note="Journal clubs", line="portfolio"),
    "mmm":  dict(name="Math, Murder, and\nMaking a Difference", href=f"{R}/activism/", x=1020, y=530, label="right",
                 kind="xfer", ret=True, note="Portfolio ⇆ Rising Tigers", line="tigers"),

    # Rising Tigers line — risingtigers.tahreemkarim.xyz (runs north–south, crossing Garden and Portfolio)
    "rti":  dict(name="Rising Tigers", href=R, x=1020, y=245, label="right", kind="hub",
                 note="Mentorship · guides", line="tigers"),
    "congo": dict(name="Congo", href=f"{R}/artifacts/congo/", x=1020, y=315, label="right", line="tigers"),
    "sudan": dict(name="Sudan", href=f"{R}/artifacts/sudan/", x=1020, y=385, label="right", line="tigers"),
    "pal":  dict(name="Palestine", href=f"{R}/artifacts/palestine/", x=1020, y=455, label="right", line="tigers"),
    "srcl": dict(name="Source library", href="https://github.com/TahreemK13/Rising_Tigers_Initiative/tree/main/library",
                 x=1020, y=610, label="right", note="GitHub", line="tigers"),
    "arti": dict(name="Artifacts index", href=f"{R}/artifacts/", x=1020, y=675, label="right", status="building", line="tigers"),
    "bang": dict(name="Bangladesh", x=1020, y=740, label="right", status="planned", note="Planned", line="tigers"),
    "arm":  dict(name="Armenia", x=1020, y=805, label="right", status="planned", note="Planned", line="tigers"),

    # Profiles — elsewhere on the internet
    "gh":   dict(name="GitHub", href="https://github.com/TahreemK13", x=240, y=430, label="left", line="profiles"),
    "li":   dict(name="LinkedIn", href="https://www.linkedin.com/in/tahreem-karim/", x=240, y=485, label="left", line="profiles"),
    "cv":   dict(name="CV", href="https://drive.google.com/file/d/1RAJkQ8-j90F0jiusWNYQVpaJC3LeLOdm/view?usp=sharing",
                 x=240, y=540, label="left", line="profiles"),
    "fl":   dict(name="Flickr", href="https://www.flickr.com/photos/tahreemkphotography/", x=240, y=595, label="left", line="profiles"),
    "ig":   dict(name="Instagram", href="https://www.instagram.com/tahreemkphoto/", x=240, y=650, label="left", line="profiles"),
    "raja": dict(name="Raja", href="https://www.instagram.com/raja.hobbes.tigerdog/", x=240, y=705, label="left", line="profiles"),
    "rli":  dict(name="RTI LinkedIn", href="https://www.linkedin.com/company/rising-tigers-initiative/", x=240, y=760,
                 label="left", line="profiles"),
    "rig":  dict(name="RTI Instagram", href="https://www.instagram.com/the_rising_tigers_initiative/", x=240, y=815,
                 label="left", line="profiles"),
}

# Each line: its track as polylines. "planned" segments draw dotted.
# A line's name tag is drawn at `tag` (x, y, anchor).
LINES = [
    dict(id="profiles", name="PROFILES", tag=(240, 858, "middle"),
         track=[[(240, 350), (240, 815)]]),
    dict(id="home", name="HOME LINE", tag=(924, 355, "start"),
         track=[[(240, 350), (900, 350)]]),
    dict(id="garden", name="GARDEN LINE", tag=(256, 262, "start"),
         track=[[(240, 350), (240, 230), (320, 150), (1020, 150)]],
         planned=[[(1020, 150), (1150, 150)]]),
    dict(id="portfolio", name="PORTFOLIO LINE", tag=(372, 452, "start"),
         track=[[(240, 350), (420, 530), (1020, 530)]]),
    dict(id="tigers", name="RISING TIGERS LINE", tag=(1020, 858, "middle"),
         track=[[(1020, 150), (1020, 675)]],
         planned=[[(1020, 675), (1020, 805)]]),
]

VIEW = (40, 82, 1210, 800)  # x, y, width, height of the visible canvas
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
