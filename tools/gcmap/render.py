"""Layout and output: place every stop, draw the SVG map, the directory and the
status block, and splice them into index.html between their markers."""
import json
from html import escape
from math import sqrt
from urllib.parse import urlsplit

from .clock import when
from .crawl import norm
from .graph import Net
from .settings import (ALIASES, AX, AY, CX, CY, DIAG, DIRS, MY_HOSTS, PACIFIC, PAGE, RINGS, VIEW)
from .stations import HUBS, IGNORE, LINES, NOTIFY_TOPIC, PROPOSED, STATIONS, UPDATE, name


def at(d, t):
    """Point at radius t (0 center, 1 outer ring) along compass direction d."""
    dx, dy = DIRS[d]
    if dx and dy:
        return CX + dx * t * DIAG, CY + dy * t * DIAG
    return CX + dx * t * AX, CY + dy * t * AY


def n(v):
    """Coordinate as short text: one decimal, no trailing zeros."""
    return f"{v:.1f}".rstrip("0").rstrip(".")


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


LETTER = {ln["id"]: ln["letter"] for ln in LINES}

BG = "var(--bg)"


def bullet(x, y, line, r=6.5, cls="bul"):
    return (f'<circle cx="{n(x)}" cy="{n(y)}" r="{r}" class="t-{line}"/>'
            f'<text x="{n(x)}" y="{n(y + r * .42)}" text-anchor="middle" class="{cls}">{LETTER[line]}</text>')


def marker(x, y, status, kind, line):
    c = f'cx="{n(x)}" cy="{n(y)}"'
    if status == "gone":  # struck through
        return (f'<circle {c} r="7" fill="{BG}" stroke="var(--muted)" stroke-width="2"/>'
                f'<path d="M{n(x - 5)},{n(y + 5)} L{n(x + 5)},{n(y - 5)}" stroke="var(--muted)" stroke-width="2"/>')
    if status == "planned":
        return f'<circle {c} r="6.5" fill="{BG}" stroke="var(--muted)" stroke-width="2" stroke-dasharray="1.5 3.5"/>'
    if status in ("building", "orphan", "provisional"):
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
    # The accessible name is an attribute, not a <title>: a <title> child makes the browser
    # pop up a native tooltip over the map, which covers the labels and fights the dwell.
    # Stops carry their route text in data-tip for the same reason; hub.js reads it.
    svg = [f'<svg class="net" viewBox="{VIEW}" xmlns="http://www.w3.org/2000/svg" '
           'aria-label="System map of Tahreem Karim\'s websites" aria-describedby="net-desc">'
           '<desc id="net-desc">Grand Central in the center; each ring is one more click away, '
           'computed from the links on every page.</desc>',
           '<g class="deco" aria-hidden="true">']

    # rings: one per click distance, labeled just under the east and west lines.
    # Each ring travels with its own labels in a group, so hovering either lights the
    # pair (hub.js and the .ring-grp rules); the transparent twin is a wide, easy
    # target for a dotted line. The labels clear the stop notes on the same row.
    svg.append('<g class="rings">')
    for i, text in enumerate(["1 click", "2 clicks"]):
        rx, ry = n(RINGS[i + 1] * AX), n(RINGS[i + 1] * AY)
        r = (RINGS[i] + RINGS[i + 1]) / 2
        svg.append(f'<g class="ring-grp"><ellipse cx="{CX}" cy="{CY}" rx="{rx}" ry="{ry}" class="ring-hit"/>'
                   f'<ellipse cx="{CX}" cy="{CY}" rx="{rx}" ry="{ry}" class="ring"/>')
        svg += [f'<text x="{n(CX + sx * r * AX * .985)}" y="{n(CY + 62 + r * 12)}" text-anchor="middle" '
                f'class="ring-label">{text.upper()}</text>' for sx in (-1, 1)]
        svg.append("</g>")
    # One PLANNED control, tucked under the Garden line tag: hovering it (or any planned
    # stop) lights every planned stop at once. Two of these, out at the ends of the east
    # and west lines, read as two separate switches for what is really one state.
    gx, gy = next((at(d, RINGS[-1] + .045) if len(ln["spokes"]) == 1 else at(d, t[keys[-1]] + .09))
                  for ln, d, keys, _ in spokes() if ln["id"] == "garden")
    svg.append(f'<g class="ring-grp ring-planned">'
               f'<rect x="{n(gx + 16)}" y="{n(gy + 12)}" width="88" height="24" class="planned-hit"/>'
               f'<text x="{n(gx + 24)}" y="{n(gy + 28)}" text-anchor="start" class="ring-label">PLANNED</text></g>')
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
        if STATIONS[a].get("edited") or STATIONS[b].get("edited"):
            cls = "link edit"
        svg.append(f'<path class="{cls}" d="{curve(pos[a], pos[b])}" stroke-width="{.8 + 3.8 * f:.2f}" '
                   f'stroke-opacity="{.1 + .42 * f:.2f}"/>')
    svg.append("</g>")

    # tracks, with a route bullet and tag at each end
    def pts(ks):
        return " ".join(f"{n(pos[k][0])},{n(pos[k][1])}" for k in ks)

    for ln, d, keys, tag in spokes():
        ks = ordered[d]
        live = [k for k in ks if STATIONS[k].get("status") not in ("planned", "provisional")]  # dotted beyond
        svg.append(f'<polyline class="net-line l-{ln["id"]}" pathLength="1" points="{pts(["gc", *live])}"/>')
        if len(live) < len(ks):
            svg.append(f'<polyline class="net-line planned l-{ln["id"]}" points="{pts([live[-1], *ks[len(live):]])}"/>')
        for a, b in zip(["gc", *live], live):  # an edited page: its stretch of track is under construction
            if STATIONS[b].get("edited"):  # dark gaps under orange dashes: visible on any line, orange included
                svg.append(f'<polyline class="net-line edit-gap" points="{pts([a, b])}"/>'
                           f'<polyline class="net-line edit" points="{pts([a, b])}"/>')
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
            tip = escape(f"{name(k)} — {hint}")
            svg.append(f'<a href="{escape(s["href"])}" {data} aria-label="{aria}" data-tip="{tip}">{body}</a>' if s.get("href") and status != "planned"
                       else f'<g class="st-planned" {data} role="img" aria-label="{aria}" data-tip="{tip}">{body}</g>')
    svg.append('<a href="/" data-k="gc" data-route="gc" style="--d:0" aria-label="Grand Central, you are here" '
               'data-tip="Grand Central — you are here">'
               f'<circle class="hit" cx="{CX}" cy="{CY}" r="34" fill="transparent" stroke="var(--{"orange" if STATIONS["gc"].get("edited") else "link"})" stroke-opacity=".25" stroke-width="2"/>'
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
            kcls = " hub" if k in HUBS else {"planned": " planned", "building": " building", "orphan": " building",
                                             "provisional": " building", "gone": " planned"}.get(status, "")
            text = escape(name(k))
            link = f'<a href="{escape(s["href"])}">{text}</a>' if s.get("href") and status != "planned" else f"<span>{text}</span>"
            buls = "".join(f'<span class="bul-i t-{b}" title="Links to the {b} line">{LETTER[b]}</span>' for b in net.bullets(k))
            clicks = f"{net.dist[k]} click{'s' * (net.dist[k] > 1)}" if k in net.dist else ""
            note = " · ".join(x for x in (clicks, s.get("note"), "edited" * bool(s.get("edited"))) if x)
            rows.append(f'          <li class="stop{kcls}"><span class="dot" aria-hidden="true"></span>{link}{buls}'
                        + (f'<span class="note">{escape(note)}</span>' if note else "") + "</li>")
        rows.append("        </ol>\n      </div>\n")
    return "\n".join(rows)


def status_block(net):
    """Under the map: the dated update notice, and what the page's "check for new
    pages" button needs as JSON (the pages to read, every URL the map already
    knows, names for any that turn up gone). The browser repeats `check`'s comparison."""
    out = []
    if UPDATE["at"]:
        t = when(UPDATE["at"]).astimezone(PACIFIC)
        stamp = f"{t:%b} {t.day}, {t.year}, {t.hour % 12 or 12}:{t:%M} {'am' if t.hour < 12 else 'pm'} {t:%Z}"
        note = f" · {escape(UPDATE['note'])}" if UPDATE["note"] else ""
        out.append(f'<p class="map-updated">Map updated <time datetime="{UPDATE["at"]}">{stamp}</time>{note}</p>')
    look = sorted({s["href"] for s in STATIONS.values() if s.get("href") and s.get("status") != "provisional"
                   and urlsplit(norm(s["href"])).netloc in MY_HOSTS})
    urls = {norm(u) for s in STATIONS.values() for u in [s.get("href"), *s.get("also", [])] if u}
    urls |= {norm(u) for u in IGNORE}
    gone_ok = {norm(STATIONS[k]["href"]) for k in STATIONS if net.status(k) == "gone" or f"remove:{k}" in IGNORE}
    data = dict(look=look, known=sorted(urls), goneOk=sorted(gone_ok), hosts=sorted(MY_HOSTS), aliases=ALIASES,
                names={norm(s["href"]): name(k) for k, s in STATIONS.items() if s.get("href")}, notify=NOTIFY_TOPIC)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).replace("</", "<\\/")
    out.append(f'<script type="application/json" id="map-known">{text}</script>')
    return "\n".join(out)


def splice(html, tag, content):
    start = html.index("-->", html.index(f"<!-- {tag}:START")) + 3
    return html[:start] + "\n" + content + "\n" + html[html.index(f"<!-- {tag}:END -->"):]


def stage():
    """Draw settled proposals, in memory only: a new page as an under-construction
    stop (kept out of the shortest-path math), an edited page's track and
    connectors in orange, a gone page struck through."""
    for k, p in PROPOSED.items():
        if p["decision"] == "no" or p["stage"] != "building":
            continue
        if p["action"] == "edit":
            STATIONS[k] = STATIONS[k] | dict(edited=True)
            continue
        if p["action"] == "remove":
            if k in STATIONS:
                STATIONS[k] = STATIONS[k] | dict(status="gone", note=f"Gone? {p['reason']}")
            continue
        STATIONS[k] = dict(name=p["name"], href=p["href"], status="provisional", note="Under construction")
        keys = next(ln for ln in LINES if ln["id"] == p["line"])["spokes"][0][1]
        planned = [i for i, x in enumerate(keys) if STATIONS[x].get("status") == "planned"]
        keys.insert(planned[0] if planned else len(keys), k)


def build():
    stage()
    net = Net()
    html = PAGE.read_text(encoding="utf-8")
    for tag, content in (("MAP", draw(net)), ("DIR", directory(net)), ("STATUS", status_block(net))):
        html = splice(html, tag, content)
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
