#!/usr/bin/env python3
"""Grand Central system map, generated from the links really on each page.

    python3 tools/build_map.py crawl   # re-read every mapped page into tools/links.json
    python3 tools/build_map.py         # redraw the map and directory in index.html

Edit STATIONS (what a stop is) and LINES (which compass spoke a stop sits on,
and its order within a ring). Positions are computed, never typed:

  rings       breadth-first search from Grand Central; a stop's ring is the
              fewest clicks it takes to reach it
  connectors  every link between two pages, weighted by edge betweenness: the
              share of all shortest routes, between every pair of stops, that
              runs through it (Brandes 2001)
  bullets     the other lines a page links to

links.json holds every <a href> in each page's nav, header, body and footer.
The generated map and directory on this page are skipped, so the map never
counts itself.
"""
import json
import re
import sys
import urllib.request
from collections import deque
from datetime import date
from functools import cache
from html import escape
from html.parser import HTMLParser
from math import sqrt
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "index.html"
LINKS = HERE / "links.json"

H = "https://www.tahreemkarim.xyz"
G = "https://garden.tahreemkarim.xyz"
R = "https://risingtigers.tahreemkarim.xyz"
P = "https://github.com/TahreemK13/portfolio"
MY_HOSTS = {"www.tahreemkarim.xyz", "garden.tahreemkarim.xyz",
            "portfolio.tahreemkarim.xyz", "risingtigers.tahreemkarim.xyz"}
ALIASES = {"https://tahreemk13.github.io/portfolio": "https://portfolio.tahreemkarim.xyz"}  # old URL, redirects

# ---------------------------------------------------------------- stations
# name    label ("\n" breaks the line in flat labels)
# href    the page; omit for a planned stop
# note    small caption (optional)
# status  building | planned (default: live)
# also    other URLs that count as this stop, e.g. files inside a folder
STATIONS = {
    "gc":    dict(name="Grand Central", href=f"{H}/"),

    "now":   dict(name="Now", href=f"{H}/now", note="Mar 2026"),
    "sci":   dict(name="Science\n& CV", href=f"{H}/science"),
    "free":  dict(name="Free\nresources", href=f"{H}/free-resources", status="building", note="No PDFs yet"),
    "art":   dict(name="Art", href=f"{H}/art", status="building", note="Soon"),
    "trav":  dict(name="Travel", href=f"{H}/travel", status="building", note="Soon"),

    "gdn":   dict(name="Digital garden", href=G),
    "lib":   dict(name="Library", href=f"{G}/library"),
    "brain": dict(name="Brainstorm with us?", href=f"{G}/posts/rti_brainstorm.html"),
    "cur":   dict(name="Online curriculum", href=f"{G}/posts/on_curriculum.html"),
    "born":  dict(name="Born with it?", href=f"{G}/posts/on-philosophy.html"),
    "mvd":   dict(name="Marvel vs. DC", href=f"{G}/posts/comics-multimodal.html", note="ML seedling"),
    "scicomm": dict(name="SciComm as design", status="planned"),

    "pf":    dict(name="Portfolio", href="https://portfolio.tahreemkarim.xyz", note="Resume PDF"),
    "age":   dict(name="Aging biomarkers", href=f"{P}/blob/main/Visualizations", note="Brown University"),
    "shm":   dict(name="SHM simulator", href=f"{P}/blob/main/Coding/SHM%20simulator%20Prototype_ntbk.ipynb", note="Notebook"),
    "sbh":   dict(name="SynBioHub parts", href="https://tahreemk13.github.io/SynBioHub_parts_visualization/", note="Interactive"),
    "m593":  dict(name="SIADS 593 Milestone I", href="https://github.com/KCYL/SIADS593-milestone1-project", note="Team repo"),
    "pres":  dict(name="Presentations", href=f"{P}/tree/main/Presentations", note="4 decks",
                  also=[f"{P}/blob/main/Presentations/{f}.pdf" for f in
                        ("MelanoBio", "TacitIntvJournClb", "ExperienceReview_Biohub", "SeanomeJCplmRAAA")]),

    "rti":   dict(name="Rising Tigers", href=R, note="Guides · causes"),
    "act":   dict(name="Math, Murder, and\nMaking a Difference", href=f"{R}/activism/"),
    "congo": dict(name="Congo", href=f"{R}/artifacts/congo/", note="+ PDF"),
    "sudan": dict(name="Sudan", href=f"{R}/artifacts/sudan/", note="+ PDF"),
    "pal":   dict(name="Palestine", href=f"{R}/artifacts/palestine/", note="+ PDF"),
    "srcl":  dict(name="Source\nlibrary", href="https://github.com/TahreemK13/Rising_Tigers_Initiative/tree/main/library", note="GitHub"),
    "rli":   dict(name="RTI\nLinkedIn", href="https://www.linkedin.com/company/rising-tigers-initiative/"),
    "rig":   dict(name="RTI\nInstagram", href="https://www.instagram.com/the_rising_tigers_initiative/"),
    "bang":  dict(name="Bangladesh", status="planned"),
    "arm":   dict(name="Armenia", status="planned"),

    "gh":    dict(name="GitHub", href="https://github.com/TahreemK13"),
    "li":    dict(name="LinkedIn", href="https://www.linkedin.com/in/tahreem-karim/"),
    "cv":    dict(name="CV", href="https://drive.google.com/file/d/1RAJkQ8-j90F0jiusWNYQVpaJC3LeLOdm/view?usp=sharing"),
    "fl":    dict(name="Flickr", href="https://www.flickr.com/photos/tahreemkphotography/"),
    "ig":    dict(name="Instagram", href="https://www.instagram.com/tahreemkphoto/"),
    "raja":  dict(name="Raja", href="https://www.instagram.com/raja.hobbes.tigerdog/", note="The whippet"),
}

# ---------------------------------------------------------------- lines
# spokes: (compass direction, stops). Within a ring, stops keep this order,
# outward from the center. A line with two spokes gets a tag per spoke.
LINES = [
    dict(id="home", letter="H", name="Home line", domain="tahreemkarim.xyz",
         spokes=[("W", ["now", "sci", "free", "art", "trav"])]),
    dict(id="garden", letter="G", name="Garden line", domain="garden.tahreemkarim.xyz",
         spokes=[("N", ["gdn", "lib", "brain", "cur", "born", "mvd", "scicomm"])]),
    dict(id="tigers", letter="T", name="Rising Tigers line", domain="risingtigers.tahreemkarim.xyz",
         spokes=[("E", ["rti", "act", "congo", "sudan", "pal", "srcl", "rli", "rig", "bang", "arm"])]),
    dict(id="portfolio", letter="P", name="Portfolio line", domain="portfolio.tahreemkarim.xyz",
         spokes=[("S", ["pf", "age", "shm", "sbh", "m593", "pres"])]),
    dict(id="profiles", letter="S", name="Profiles shuttle", domain="Elsewhere",
         spokes=[("SW", ["gh", "li", "cv"], "Profiles"), ("SE", ["fl", "ig", "raja"], "Photo")]),
]
HUBS = {"gdn", "pf", "rti"}  # a site's front page: drawn with a ring in its line color

# ---------------------------------------------------------------- geometry
CX, CY = 700, 520                  # Grand Central
AX, AY = 640, 440                  # outer radius, horizontal and vertical
RINGS = [0.12, 0.56, 0.90, 1.00]   # ring edges: 1 click | 2 clicks | planned
HALF = (700, 490)                  # half-width and half-height of the frame around Grand Central
VIEW = f"{CX - HALF[0]} {CY - HALF[1]} {2 * HALF[0]} {2 * HALF[1]}"  # centered on the hub
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0), "SE": (1, 1), "SW": (-1, 1)}
DIAG = AX * AY / sqrt(AX * AX + AY * AY)  # where a 45° spoke meets each ring


def at(d, t):
    """Point at radius t (0 center, 1 outer ring) along compass direction d."""
    dx, dy = DIRS[d]
    if dx and dy:
        return CX + dx * t * DIAG, CY + dy * t * DIAG
    return CX + dx * t * AX, CY + dy * t * AY


def n(v):
    """Coordinate as short text: one decimal, no trailing zeros."""
    return f"{v:.1f}".rstrip("0").rstrip(".")


def name(k):
    return STATIONS[k]["name"].replace("\n", " ")


# ---------------------------------------------------------------- crawling
def norm(url, base=H + "/"):
    """Canonical URL, so one page always compares equal to itself."""
    s = urlsplit(urljoin(base, url.strip()))
    if s.scheme not in ("http", "https"):
        return None
    host = s.netloc.lower()
    if host == "tahreemkarim.xyz":
        host = "www." + host
    path = re.sub(r"(/index)?\.html$", "", s.path).rstrip("/")
    if host in ("github.com", "tahreemk13.github.io"):
        path = path.lower()
    url = urlunsplit(("https", host, path, "", ""))
    return ALIASES.get(url, url)


class Anchors(HTMLParser):
    """Every <a href>, tagged with the nav/header/footer it sits in (else body)."""
    SECTIONS = ("nav", "header", "footer")

    def __init__(self):
        super().__init__()
        self.stack, self.found = [], []

    def handle_starttag(self, tag, attrs):
        if tag in self.SECTIONS:
            self.stack.append(tag)
        href = dict(attrs).get("href") if tag == "a" else None
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            self.found.append((self.stack[-1] if self.stack else "body", href))

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass


def extract(html, page_url):
    html = re.sub(r"<!-- (MAP|DIR):START.*?<!-- \1:END -->", "", html, flags=re.S)
    parser = Anchors()
    parser.feed(html)
    links = {}
    for section, href in parser.found:
        url = norm(href, page_url)
        if url and url not in links.setdefault(section, []):
            links[section].append(url)
    return links


def crawl():
    pages = {}
    for s in STATIONS.values():
        url = norm(s["href"]) if s.get("href") else None
        if not url or urlsplit(url).netloc not in MY_HOSTS or url in pages:
            continue
        try:
            req = urllib.request.Request(s["href"], headers={"User-Agent": "grand-central-map"})
            with urllib.request.urlopen(req, timeout=20) as r:
                pages[url] = dict(status=r.status, links=extract(r.read().decode("utf-8", "replace"), r.url))
        except urllib.error.HTTPError as e:
            pages[url] = dict(status=e.code, links={})
        except OSError as e:
            pages[url] = dict(status=0, error=str(e), links={})
        print(f"{pages[url]['status']:>4}  {url}")
    LINKS.write_text(json.dumps(dict(crawled=str(date.today()), pages=pages), indent=1) + "\n")
    print(f"Saved {len(pages)} pages to {LINKS}")


# ---------------------------------------------------------------- graph
class Net:
    """The link graph between stops, and everything derived from it."""

    def __init__(self):
        data = json.loads(LINKS.read_text())
        self.crawled_on, self.pages = data["crawled"], data["pages"]
        self.line = {"gc": "home"} | {k: ln["id"] for ln in LINES for sp in ln["spokes"] for k in sp[1]}
        by_url = {norm(u): k for k, s in STATIONS.items() for u in [s.get("href"), *s.get("also", [])] if u}
        self.out, self.strays, self.crawled = {}, {}, set()
        for k, s in STATIONS.items():
            page = self.pages.get(norm(s["href"])) if s.get("href") else None
            urls = [u for sec in (page or {}).get("links", {}).values() for u in sec]
            if page:
                self.crawled.add(k)
            self.out[k] = {by_url[u] for u in urls if u in by_url} - {k}
            stray = {u for u in urls if urlsplit(u).netloc in MY_HOSTS and u not in by_url and not u.endswith(".pdf")}
            if stray:
                self.strays[k] = sorted(stray)
        self.dist, self.prev = self.bfs("gc")

    def bfs(self, src):
        """Fewest clicks from src to every stop; ties prefer staying on one line."""
        dist, prev, q = {src: 0}, {}, deque([src])
        while q:
            a = q.popleft()
            for b in sorted(self.out[a], key=lambda b: (self.line[b] != self.line[a], b)):
                if b not in dist:
                    dist[b], prev[b] = dist[a] + 1, a
                    q.append(b)
        return dist, prev

    def betweenness(self):
        """Brandes' algorithm, credited to links: for every ordered pair of stops,
        each link's share of the shortest paths between them. O(stops × links)."""
        eb = {}
        for src in sorted(self.out):  # sorted everywhere: same input, same file
            dist, sigma, preds, order, q = {src: 0}, {src: 1}, {src: []}, [], deque([src])
            while q:  # BFS, counting shortest paths (sigma)
                v = q.popleft()
                order.append(v)
                for w in sorted(self.out[v]):
                    if w not in dist:
                        dist[w], sigma[w], preds[w] = dist[v] + 1, 0, []
                        q.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)
            delta = dict.fromkeys(order, 0.0)
            for w in reversed(order):  # push dependencies back toward src
                for v in preds[w]:
                    c = sigma[v] / sigma[w] * (1 + delta[w])
                    edge = tuple(sorted((v, w)))
                    eb[edge] = eb.get(edge, 0) + c
                    delta[v] += c
        return eb

    def status(self, k):
        s = STATIONS[k].get("status", "live")
        return "orphan" if s != "planned" and k not in self.dist else s

    def route(self, k):
        """Stops from Grand Central to k along the shortest path."""
        p = [k]
        while p[-1] in self.prev:
            p.append(self.prev[p[-1]])
        return p[::-1]

    @cache
    def hint(self, k):
        if k in self.dist:
            c = self.dist[k]
            path = " → ".join(name(x) for x in self.route(k))
            h = f"{c} click{'s' * (c > 1)}: {path}"
        else:
            h = {"planned": "planned", "orphan": "not linked from any mapped page"}[self.status(k)]
        return h + " (under construction)" * (self.status(k) == "building")

    @cache
    def bullets(self, k):
        """Other lines this page links to. Profiles count; an outside page that
        merely belongs to a line (RTI's LinkedIn) doesn't count as that line."""
        if k == "gc" or k not in self.crawled:
            return []
        hit = {self.line[b] for b in self.out[k]
               if self.line[b] == "profiles" or urlsplit(norm(STATIONS[b]["href"])).netloc in MY_HOSTS}
        return tuple(ln["id"] for ln in LINES if ln["id"] in hit - {self.line[k]})

    def kind(self, k):
        if k in HUBS:
            return "hub"
        return "xfer" if set(self.bullets(k)) - {"profiles"} else "stop"


# ---------------------------------------------------------------- layout
def layout(net):
    """Radius t of every stop: its ring from click distance, evenly spaced inside it."""
    t, last = {}, len(RINGS) - 2
    for ln in LINES:
        for d, keys, *_ in ln["spokes"]:
            rings = {}
            for k in keys:
                ring = min(net.dist[k], last) if k in net.dist else last
                rings.setdefault(ring, []).append(k)
            for r, ks in rings.items():
                for i, k in enumerate(ks):
                    t[k] = RINGS[r - 1] + (i + .5) / len(ks) * (RINGS[r] - RINGS[r - 1])
    return t


def spokes():
    """(line, direction, stops, tag) for every spoke."""
    for ln in LINES:
        for d, keys, *tag in ln["spokes"]:
            yield ln, d, keys, (tag[0] if tag else ln["name"]).upper()


def side_for(d, i):
    """Label side: E/W labels run at 45° (the hub nearest the center stays flat),
    N/S alternate left and right, diagonals face outward."""
    if d in ("E", "W"):
        return "below" if i == 0 else "rot-" + d.lower()
    if d in ("N", "S"):
        return ("left", "right")[i % 2]
    return "left" if "W" in d else "right"


# ---------------------------------------------------------------- drawing
LETTER = {ln["id"]: ln["letter"] for ln in LINES}
BG = "var(--bg)"


def bullet(x, y, line, r=6.5, cls="bul"):
    return (f'<circle cx="{n(x)}" cy="{n(y)}" r="{r}" class="t-{line}"/>'
            f'<text x="{n(x)}" y="{n(y + r * .42)}" text-anchor="middle" class="{cls}">{LETTER[line]}</text>')


def marker(x, y, status, kind, line):
    c = f'cx="{n(x)}" cy="{n(y)}"'
    if status == "planned":
        return f'<circle {c} r="6.5" fill="{BG}" stroke="var(--muted)" stroke-width="2" stroke-dasharray="1.5 3.5"/>'
    if status in ("building", "orphan"):
        return f'<circle {c} r="7" fill="{BG}" stroke="var(--orange)" stroke-width="2.5" stroke-dasharray="3 3"/>'
    if kind == "hub":
        return f'<circle {c} r="10" fill="var(--fg)" stroke="var(--line-{line})" stroke-width="4"/>'
    if kind == "xfer":  # links to another line: white interchange circle
        return (f'<circle {c} r="8" fill="var(--fg)" stroke="{BG}" stroke-width="3"/>'
                f'<circle {c} r="9.5" fill="none" stroke="var(--fg)" stroke-width="1.2"/>')
    return f'<circle {c} r="4.5" fill="var(--fg)" stroke="{BG}" stroke-width="2"/>'


def label_45(x, y, text, note, side, bullets):
    """One-line label at 45°, name nearest the stop, like a transit strip map."""
    east = side == "rot-e"
    sign, anchor = (1, "start") if east else (-1, "end")
    ax, ay = x + 7 * sign, y - 11
    out = [f'<g transform="rotate({-45 * sign} {n(ax)} {n(ay)})">',
           f'<text x="{n(ax)}" y="{n(ay)}" text-anchor="{anchor}" class="st-name">{escape(text)}</text>']
    cur = ax + sign * (len(text) * 7.4 + 8)
    for ln in bullets:
        out.append(bullet(cur + 7 * sign, ay - 5, ln))
        cur += 16 * sign
    if note:
        out.append(f'<text x="{n(cur + 3 * sign)}" y="{n(ay - 1)}" text-anchor="{anchor}" class="st-note">{escape(note)}</text>')
    return "".join(out) + "</g>"


def label(x, y, k, side, bullets, note):
    if side.startswith("rot"):
        return label_45(x, y, name(k), note, side, bullets)
    rows, lh = STATIONS[k]["name"].split("\n"), 16
    h = len(rows) * lh + (17 if note or bullets else 0)
    if side == "below":
        ax, anchor, top = x, "middle", y + 16
    else:
        ax, anchor, top = (x + 17, "start", y - h / 2) if side == "right" else (x - 17, "end", y - h / 2)
    out = [f'<text x="{n(ax)}" y="{n(top + 12 + i * lh)}" text-anchor="{anchor}" class="st-name">{escape(t)}</text>'
           for i, t in enumerate(rows)]
    if note or bullets:
        ry = top + len(rows) * lh + 8
        bw, nw = len(bullets) * 16, (len(note) * 7.1 + 5 * bool(bullets)) if note else 0
        start = {"start": ax, "end": ax - bw - nw, "middle": ax - (bw + nw) / 2}[anchor]
        out += [bullet(start + 7 + i * 16, ry, ln) for i, ln in enumerate(bullets)]
        if note:
            out.append(f'<text x="{n(start + bw + 5 * bool(bullets))}" y="{n(ry + 4)}" class="st-note">{escape(note)}</text>')
    return "".join(out)


def curve(a, b):
    """Quadratic curve between two points, bowed away from Grand Central."""
    (x1, y1), (x2, y2) = a, b
    mx, my, dx, dy = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) * .14, (y2 - y1) * .14
    qx, qy = max((mx - dy, my + dx), (mx + dy, my - dx), key=lambda c: (c[0] - CX) ** 2 + (c[1] - CY) ** 2)
    return f"M{n(x1)},{n(y1)} Q{n(qx)},{n(qy)} {n(x2)},{n(y2)}"


def draw(net):
    t = layout(net)
    pos = {k: at(d, t[k]) for _, d, keys, _ in spokes() for k in keys} | {"gc": (CX, CY)}
    ordered = {d: sorted(keys, key=t.get) for _, d, keys, _ in spokes()}
    svg = [f'<svg class="net" viewBox="{VIEW}" xmlns="http://www.w3.org/2000/svg" aria-labelledby="net-title net-desc">'
           '<title id="net-title">System map of Tahreem Karim\'s websites</title>'
           '<desc id="net-desc">Grand Central in the center; each ring is one more click away, '
           'computed from the links on every page.</desc>',
           '<g class="deco" aria-hidden="true">']

    # rings: one per click distance, labeled just under the east and west lines
    svg.append('<g class="rings">')
    svg += [f'<ellipse cx="{CX}" cy="{CY}" rx="{n(r * AX)}" ry="{n(r * AY)}" class="ring"/>' for r in RINGS[1:-1]]
    for i, text in enumerate(["1 click", "2 clicks", "planned"]):
        r = (RINGS[i] + RINGS[i + 1]) / 2
        svg += [f'<text x="{n(CX + sx * r * AX * .985)}" y="{n(CY + 50 + r * 12)}" text-anchor="middle" '
                f'class="ring-label">{text.upper()}</text>' for sx in (-1, 1)]
    svg.append("</g>")

    # connectors: links between pages, weighted by shortest-path traffic. Grand
    # Central's own links and links between neighbors on a track are left out:
    # the rings and tracks already show them.
    track = {tuple(sorted(p)) for ks in ordered.values() for p in zip(["gc", *ks], ks)}
    eb = {e: v for e, v in net.betweenness().items() if "gc" not in e and e not in track}
    top = max(eb.values(), default=1)
    svg.append('<g class="links">')
    for (a, b), v in sorted(eb.items(), key=lambda e: (round(e[1], 6), e[0])):
        f = sqrt(v / top)
        cls = f"link l-{net.line[a]}" if net.line[a] == net.line[b] else "link"
        svg.append(f'<path class="{cls}" d="{curve(pos[a], pos[b])}" stroke-width="{.8 + 3.8 * f:.2f}" '
                   f'stroke-opacity="{.1 + .42 * f:.2f}"/>')
    svg.append("</g>")

    # tracks, with a route bullet and tag at each end
    def pts(ks):
        return " ".join(f"{n(pos[k][0])},{n(pos[k][1])}" for k in ks)

    for ln, d, keys, tag in spokes():
        ks = ordered[d]
        live = [k for k in ks if STATIONS[k].get("status") != "planned"]
        svg.append(f'<polyline class="net-line l-{ln["id"]}" pathLength="1" points="{pts(["gc", *live])}"/>')
        if len(live) < len(ks):
            svg.append(f'<polyline class="net-line planned l-{ln["id"]}" points="{pts([live[-1], *ks[len(live):]])}"/>')
        ex, ey = at(d, RINGS[-1] + .045) if len(ln["spokes"]) == 1 else at(d, t[keys[-1]] + .09)
        svg.append(bullet(ex, ey, ln["id"], r=14, cls="bul-big"))
        dx, dy = DIRS[d]
        tx, ty, anchor = ((ex + dx * 22, ey + 24, "end" if dx < 0 else "start") if dx and dy else
                          (ex + 24, ey + 4, "start") if dy else
                          (ex - dx * 18, ey + 34, "end" if dx > 0 else "start"))
        svg.append(f'<text x="{n(tx)}" y="{n(ty)}" text-anchor="{anchor}" class="st-tag t-{ln["id"]}">{escape(tag)}</text>')
    svg.append("</g>")

    # stops
    for ln, d, _, _ in spokes():
        for i, k in enumerate(ordered[d]):
            s, status, (x, y) = STATIONS[k], net.status(k), pos[k]
            note = "Not linked anywhere" if status == "orphan" else s.get("note")
            hit = f'<circle class="hit" cx="{n(x)}" cy="{n(y)}" r="15" fill="transparent"/>' * (status != "planned")
            body = hit + marker(x, y, status, net.kind(k), ln["id"]) + label(x, y, k, side_for(d, i), net.bullets(k), note)
            data = f'data-k="{k}" style="--d:{min(net.dist.get(k, 3), 3)}"' + (f' data-route="{" ".join(net.route(k))}"' if k in net.dist else "")
            hint = net.hint(k)
            aria = escape(f"{name(k)}, {hint}")
            tip = f"<title>{escape(name(k))} — {escape(hint)}</title>"
            svg.append(f'<a href="{escape(s["href"])}" {data} aria-label="{aria}">{tip}{body}</a>' if s.get("href") and status != "planned"
                       else f'<g class="st-planned" {data} role="img" aria-label="{aria}">{tip}{body}</g>')
    svg.append('<a href="/" data-k="gc" data-route="gc" style="--d:0" aria-label="Grand Central, you are here">'
               '<title>Grand Central — you are here</title>'
               f'<circle class="hit" cx="{CX}" cy="{CY}" r="34" fill="transparent" stroke="var(--link)" stroke-opacity=".25" stroke-width="2"/>'
               f'<circle cx="{CX}" cy="{CY}" r="22" fill="var(--fg)" stroke="{BG}" stroke-width="5"/>'
               f'<text x="{CX + 30}" y="{CY - 44}" class="st-gc">Grand Central</text>'
               f'<text x="{CX + 30}" y="{CY - 28}" class="st-note">You are here</text></a></svg>')
    return "\n".join(svg)


def directory(net):
    rows = []
    for ln in LINES:
        cls = "" if ln["id"] == "home" else " " + ln["id"]
        rows.append(f'      <div class="route{cls}">\n        <h3>{escape(ln["name"])}<small>{escape(ln["domain"])}</small></h3>\n'
                    '        <ol class="stops">')
        keys = [k for sp in ln["spokes"] for k in sp[1]]
        for k in sorted(keys, key=lambda k: net.dist.get(k, 99)):
            s, status = STATIONS[k], net.status(k)
            kcls = " hub" if k in HUBS else {"planned": " planned", "building": " building", "orphan": " building"}.get(status, "")
            text = escape(name(k))
            link = f'<a href="{escape(s["href"])}">{text}</a>' if s.get("href") and status != "planned" else f"<span>{text}</span>"
            buls = "".join(f'<span class="bul-i t-{b}" title="Links to the {b} line">{LETTER[b]}</span>' for b in net.bullets(k))
            clicks = f"{net.dist[k]} click{'s' * (net.dist[k] > 1)}" if k in net.dist else ""
            note = " · ".join(x for x in (clicks, s.get("note")) if x)
            rows.append(f'          <li class="stop{kcls}"><span class="dot" aria-hidden="true"></span>{link}{buls}'
                        + (f'<span class="note">{escape(note)}</span>' if note else "") + "</li>")
        rows.append("        </ol>\n      </div>\n")
    return "\n".join(rows)


def splice(html, tag, content):
    start = html.index("-->", html.index(f"<!-- {tag}:START")) + 3
    return html[:start] + "\n" + content + "\n" + html[html.index(f"<!-- {tag}:END -->"):]


def main():
    if sys.argv[1:] == ["crawl"]:
        return crawl()
    net = Net()
    html = splice(splice(PAGE.read_text(encoding="utf-8"), "MAP", draw(net)), "DIR", directory(net))
    PAGE.write_text(html, encoding="utf-8")
    print(f"Map written to {PAGE} from links crawled {net.crawled_on}")
    for k in STATIONS:
        if net.status(k) == "orphan":
            print(f"  ! {k}: not reachable from Grand Central")
    for url, page in net.pages.items():
        if page.get("status") != 200:
            print(f"  ! {url}: HTTP {page.get('status')}")
    for k, urls in net.strays.items():
        print(f"  · {k} links to pages not on the map: " + ", ".join(u.split("//")[1] for u in urls))


if __name__ == "__main__":
    main()
