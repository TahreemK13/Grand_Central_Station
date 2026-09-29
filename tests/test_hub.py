#!/usr/bin/env python3
"""Quality gates for the hub. Prints a report; exits 1 if any gate fails.

    python3 tests/test_hub.py            # static checks and rendering
    python3 tests/test_hub.py --online   # also: every link to my sites and repos resolves

Rendering needs Playwright: pip install playwright pyflakes && playwright install chromium.
A preview of the map is saved to tools/.preview/map.png.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "index.html"
sys.path.insert(0, str(ROOT / "tools"))
from gcmap import crawl as bm  # noqa: E402  (norm, fetch, MY_HOSTS)

BUDGET = dict(page_kb=160, svg_elements=2500, render_s=3.0)  # generous today; raise them on purpose, not by drift
VIEWPORTS = [(390, 844), (768, 1024), (1440, 900), (1920, 1080)]
failures, notes = [], []


def gate(ok, message):
    (notes if ok else failures).append(("ok  " if ok else "FAIL") + "  " + message)


# ---------------------------------------------------------------- static
def lint():
    try:
        files = [*(ROOT / "tools").rglob("*.py"), *(ROOT / "tests").rglob("*.py")]
        r = subprocess.run([sys.executable, "-m", "pyflakes", *map(str, files)],
                           capture_output=True, text=True)
        gate(r.returncode == 0, "Python lint (pyflakes)" + (": " + r.stdout.strip() if r.returncode else ""))
    except FileNotFoundError:
        gate(False, "Python lint: pyflakes isn't installed")


def unused_css():
    html = PAGE.read_text(encoding="utf-8")
    css = html[html.index("<style>"):html.index("</style>")]
    rest = html[html.index("</style>"):] + (ROOT / "hub.js").read_text(encoding="utf-8")  # markup and the page's script
    selectors = re.sub(r"\{[^{}]*\}", "{}", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    classes = {c for c in re.findall(r"\.([a-zA-Z][\w-]*)", selectors)}
    used = set(re.findall(r'class="([^"]*)"', rest)) | set(re.findall(r"class=\\?'([^']*)'", rest))
    words = {w for group in used for w in group.split()} | set(re.findall(r"['\"]([a-z][\w-]*)['\"]", rest))
    generated = set(re.findall(r'class="([^"{]*)', (ROOT / "tools/gcmap/render.py").read_text()))  # classes the build emits
    words |= {w for g in generated for w in g.split()} | {"edit", "edit-gap", "st-planned", "pre", "go", "tracing", "on", "js", "open"}
    unused = sorted(c for c in classes if c not in words)
    gate(not unused, "No unused CSS classes" + (f": {', '.join(unused)}" if unused else ""))


def budgets():
    size = PAGE.stat().st_size / 1024
    gate(size <= BUDGET["page_kb"], f"Page size {size:.0f} KB ≤ {BUDGET['page_kb']} KB")
    svg = re.search(r"<svg class=\"net\".*?</svg>", PAGE.read_text(encoding="utf-8"), re.S).group(0)
    count = len(re.findall(r"<[a-z]", svg))
    gate(count <= BUDGET["svg_elements"], f"Map has {count} SVG elements ≤ {BUDGET['svg_elements']}")
    t = time.perf_counter()
    subprocess.run([sys.executable, str(ROOT / "tools/build_map.py")], check=True, capture_output=True)
    took = time.perf_counter() - t
    gate(took <= BUDGET["render_s"], f"Render took {took:.2f} s ≤ {BUDGET['render_s']} s")


def local_links():
    """Every same-site link, script and image on every root page points at a file,
    and every #anchor at an id."""
    broken = []
    for page in sorted(ROOT.glob("*.html")):
        html = page.read_text(encoding="utf-8")
        ids = set(re.findall(r'\sid="([^"]+)"', html))
        refs = set(re.findall(r'(?:href|src)="([^"]+)"', html))
        refs |= {"/" + r for r in re.findall(r'src="([^"/:#][^":]*)"', html)}  # relative script/image paths
        for href in sorted(refs):
            if href.startswith("#"):
                if href[1:] and href[1:] not in ids:
                    broken.append(f"{page.name}: {href}")
                continue
            if not href.startswith("/") or href.startswith("//"):
                continue
            if href == "/images/raja-404.jpg" or href.startswith("/images/raja"):
                continue  # the 404 photo is uploaded by hand; the page shows a frame until it exists
            path, _, frag = href.partition("#")
            target = ROOT / path.lstrip("/")
            found = next((c for c in (target / "index.html", target.with_suffix(".html"), target) if c.is_file()), None)
            if not found:
                broken.append(f"{page.name}: {href}")
            elif frag and f'id="{frag}"' not in found.read_text(encoding="utf-8", errors="replace"):
                broken.append(f"{page.name}: {href} (no #{frag})")
    gate(not broken, "Same-site links and anchors resolve" + (": " + "; ".join(broken) if broken else ""))


def data_block():
    m = re.search(r'<script type="application/json" id="map-known">(.*?)</script>', PAGE.read_text(encoding="utf-8"), re.S)
    try:
        data = json.loads(m.group(1).replace("<\\/", "</"))
        ok = all(urlsplit(u).netloc in bm.MY_HOSTS for u in data["look"])
        gate(ok, f"Live-check data parses; it reads {len(data['look'])} pages, all on my sites")
    except (AttributeError, ValueError, KeyError) as e:
        gate(False, f"Live-check data block: {e}")


def online():
    """Links to my own sites and repos from any root page answer 200. Social sites
    refuse robots, so they're counted and skipped."""
    hrefs = set()
    for page in ROOT.glob("*.html"):
        hrefs |= {bm.norm(h) for h in re.findall(r'href="(https?://[^"]+)"', page.read_text(encoding="utf-8"))}
    mine = sorted(u for u in hrefs if u and (urlsplit(u).netloc in bm.MY_HOSTS or u.startswith("https://github.com/tahreemk13")))
    bad = [f"{u} ({s})" for u in mine if (s := bm.fetch(u)[0]) != 200]
    gate(not bad, f"{len(mine)} links to my sites and repos resolve" + (": " + "; ".join(bad) if bad else "")
         + f" ({len(hrefs) - len(mine)} other links not checked)")


# ---------------------------------------------------------------- rendering
LABELS_JS = """() => {
  // Each label's corners on screen, rotation included.
  const out = [];
  for (const t of document.querySelectorAll('svg.net text')) {
    const b = t.getBBox(), m = t.getScreenCTM();
    if (!b.width || !m) continue;
    const pt = (x, y) => ({ x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f });
    const i = 1;  // shrink by a pixel: touching isn't overlapping
    out.push({ text: t.textContent, stop: t.closest('[data-k]')?.dataset.k || '',
      c: [pt(b.x + i, b.y + i), pt(b.x + b.width - i, b.y + i), pt(b.x + b.width - i, b.y + b.height - i), pt(b.x + i, b.y + b.height - i)] });
  }
  return out;
}"""


def overlaps(a, b):
    """Separating-axis test for two convex quads."""
    for poly in (a, b):
        for i in range(4):
            p, q = poly[i], poly[(i + 1) % 4]
            ax, ay = q["y"] - p["y"], p["x"] - q["x"]
            pa = [ax * v["x"] + ay * v["y"] for v in a]
            pb = [ax * v["x"] + ay * v["y"] for v in b]
            if max(pa) < min(pb) or max(pb) < min(pa):
                return False
    return True


def live_check(page):
    """The home page's "Check for new pages" button, against the approved
    snapshot served as the live web: it must find nothing new."""
    pages = json.loads((ROOT / "tools/links.json").read_text())["pages"] if (ROOT / "tools/links.json").exists() else {}

    def serve(route):
        url = bm.norm(route.request.url)
        if route.request.url.startswith("file:"):
            return route.continue_()
        if url not in pages:
            return route.fulfill(status=404, headers={"access-control-allow-origin": "*"}, body="")
        body = "".join(f'<a href="{u}">x</a>' for sec in pages[url]["links"].values() for u in sec)
        route.fulfill(status=200, headers={"access-control-allow-origin": "*", "content-type": "text/html"},
                      body=f"<html><body>{body}</body></html>")
    page.unroute("**/*")
    page.route("**/*", serve)
    page.click("#scan-btn")
    page.wait_for_function("!document.getElementById('scan-btn').hasAttribute('aria-busy')", timeout=15000)
    result = page.inner_text("#scan-out")
    gate(result.startswith("No new pages found"), f"Live-check button agrees with the snapshot: “{result[:60]}”")


def render():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        gate(False, "Rendering: Playwright isn't installed")
        return
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w, h in VIEWPORTS:
            page = browser.new_page(viewport={"width": w, "height": h}, reduced_motion="reduce")
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("console", lambda m: m.type == "error" and "net::" not in m.text and "Failed to load" not in m.text
                    and errors.append(m.text))
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
            page.goto(PAGE.as_uri())
            page.evaluate("document.getElementById('map').scrollIntoView()")
            page.wait_for_timeout(200)
            r = page.evaluate("""() => {
              const c = document.querySelector('[data-k=gc] .hit').getBoundingClientRect();
              const s = document.querySelector('.map-scroll').getBoundingClientRect();
              return { gc: c.x + c.width / 2, mid: s.x + s.width / 2,
                       hscroll: document.documentElement.scrollWidth > innerWidth,
                       minHit: Math.min(...[...document.querySelectorAll('svg.net .hit')].map(e => e.getBoundingClientRect().width)) };
            }""")
            gate(not errors, f"{w}×{h}: no script errors" + (": " + "; ".join(errors[:3]) if errors else ""))
            gate(not r["hscroll"], f"{w}×{h}: no sideways page scroll")
            gate(abs(r["gc"] - r["mid"]) <= 1.5, f"{w}×{h}: Grand Central centered ({r['gc'] - r['mid']:+.1f} px)")
            if w == 390:
                gate(r["minHit"] >= 23.5, f"{w}×{h}: every stop is at least a 24 px target ({r['minHit']:.1f})")
            if w == 1440:
                labels = page.evaluate(LABELS_JS)
                hits = [f"“{a['text']}” × “{b['text']}”" for i, a in enumerate(labels) for b in labels[i + 1:]
                        if overlaps(a["c"], b["c"])]
                gate(not hits, f"{w}×{h}: {len(labels)} labels, none overlapping" + (": " + "; ".join(hits[:6]) if hits else ""))
                (ROOT / "tools/.preview").mkdir(exist_ok=True)
                page.locator("svg.net").screenshot(path=str(ROOT / "tools/.preview/map.png"))
                live_check(page)
            page.close()
        for other in sorted(ROOT.glob("*.html")):
            if other == PAGE:
                continue
            page, errors = browser.new_page(), []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
            page.goto(other.as_uri())
            gate(not errors, f"{other.name}: no script errors" + (": " + errors[0] if errors else ""))
            page.close()
        browser.close()


if __name__ == "__main__":
    for check in (lint, unused_css, budgets, local_links, data_block, *(online,) * ("--online" in sys.argv), render):
        check()
    print("\n".join(notes + failures))
    print(f"\n{len(notes)} passed, {len(failures)} failed")
    sys.exit(1 if failures else 0)
