"""The link graph between stops: breadth-first click distance, Brandes' edge
betweenness, and the before/after report of how a change moved shortest paths."""
import json
from collections import deque
from functools import cache
from urllib.parse import urlsplit

from .crawl import norm
from .settings import LINKS, MY_HOSTS
from .stations import HUBS, LINES, STATIONS, name


class Net:
    """The link graph between stops, and everything derived from it."""

    def __init__(self):
        data = json.loads(LINKS.read_text()) if LINKS.exists() else dict(crawled="never", pages={})
        self.crawled_on, self.pages = data["crawled"], data["pages"]
        self.line = {"gc": "home"} | {k: ln["id"] for ln in LINES for sp in ln["spokes"] for k in sp[1]}
        real = {k for k, s in STATIONS.items() if s.get("status") != "provisional"}  # the rest wait for approval
        by_url = {norm(u): k for k in real for u in [STATIONS[k].get("href"), *STATIONS[k].get("also", [])] if u}
        self.out, self.strays, self.crawled = {}, {}, set()
        for k, s in STATIONS.items():
            page = self.pages.get(norm(s["href"])) if s.get("href") and k in real else None
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
        return "orphan" if s in ("live", "building") and k not in self.dist else s

    def route(self, k):
        """Stops from Grand Central to k along the shortest path."""
        p = [k]
        while p[-1] in self.prev:
            p.append(self.prev[p[-1]])
        return p[::-1]

    @cache
    def hint(self, k):
        status = self.status(k)
        if k in self.dist:
            c = self.dist[k]
            path = " → ".join(name(x) for x in self.route(k))
            h = f"{c} click{'s' * (c > 1)}: {path}"
        else:
            h = {"planned": "planned", "provisional": "under construction: joins the map once approved"}.get(
                status, "not linked from any mapped page")
        h += {"building": " (under construction)", "gone": " (page is gone, awaiting approval)"}.get(status, "")
        return h + " (edited, awaiting approval)" * bool(STATIONS[k].get("edited"))

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


def stats():
    """The graph as plain data: rings, every pair's shortest path, link betweenness."""
    net = Net()
    nodes = sorted(k for k in net.dist)
    pairs = {f"{a}>{b}": d for a in nodes for b, d in net.bfs(a)[0].items() if b != a}
    return dict(ring=net.dist, pairs=pairs, eb={f"{a}|{b}": round(v, 2) for (a, b), v in net.betweenness().items()},
                names={k: name(k) for k in STATIONS}, route={k: " → ".join(name(x) for x in net.route(k)) for k in nodes})


def impact(b, a):
    """Markdown: how the change moved shortest paths between every pair of stops."""
    mean = lambda p: sum(p.values()) / len(p) if p else 0  # noqa: E731
    both = set(b["pairs"]) & set(a["pairs"])
    shorter = sum(a["pairs"][p] < b["pairs"][p] for p in both)
    longer = sum(a["pairs"][p] > b["pairs"][p] for p in both)
    rows = [("Stops on the graph", len(b["ring"]), len(a["ring"])),
            ("Connected ordered pairs", len(b["pairs"]), len(a["pairs"])),
            ("Mean shortest path, clicks", f"{mean(b['pairs']):.2f}", f"{mean(a['pairs']):.2f}"),
            ("Longest shortest path", max(b["pairs"].values(), default=0), max(a["pairs"].values(), default=0))]
    out = ["### Effect on shortest paths\n", "| | Before | After |", "| --- | ---: | ---: |",
           *[f"| {r} | {x} | {y} |" for r, x, y in rows], ""]
    for k in sorted(set(a["ring"]) - set(b["ring"])):
        out.append(f"- **Joins** at {a['ring'][k]} click{'s' * (a['ring'][k] > 1)}: {a['route'][k]}")
    for k in sorted(set(b["ring"]) - set(a["ring"])):
        out.append(f"- **Leaves:** {b['names'][k]}")
    for k in sorted(set(a["ring"]) & set(b["ring"])):
        if a["ring"][k] != b["ring"][k]:
            out.append(f"- **Moves** from {b['ring'][k]} to {a['ring'][k]} clicks: {a['names'][k]}")
    out.append(f"- {shorter} existing pairs got closer and {longer} got farther apart.")
    top = sorted(a["eb"].items(), key=lambda e: (-e[1], e[0]))[:5]
    out += ["", "**Busiest connectors** (shortest paths through each link, and the change):", ""]
    for e, v in top:
        x, y = e.split("|")
        out.append(f"- {a['names'][x]} ↔ {a['names'][y]}: {v:g} ({v - b['eb'].get(e, 0):+.1f})")
    return "\n".join(out)
