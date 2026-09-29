"""The lifecycle: `check` finds new, edited and gone pages and draws them once
they settle; `apply` carries out your decisions and recomputes the graph;
`verify` guards integrity and reproducibility."""
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .clock import iso, now, pt, when
from .crawl import pushed, read, repo, norm
from .graph import impact
from .render import spokes
from .settings import CLI, FILES, GH_REPO, LINKS, MY_HOSTS, PAGE, SETTLE
from .stations import HOST_LINE, HUBS, IGNORE, LINES, PROPOSED, STATIONS, name

SOURCE = Path(__file__).with_name("stations.py")  # `check` and `apply` edit its source


def slug(url, taken):
    """Short unique station key: a repo's name, or a page's last path segment."""
    gh = GH_REPO.match(url)
    last = f"{gh.group(1)}{'-readme' * bool(gh.group(2))}" if gh else urlsplit(url).path.rsplit("/", 1)[-1]
    base = re.sub(r"[^a-z0-9]+", "-", last.lower()).strip("-")[:32] or "page"
    k, i = base, 2
    while k in taken:
        k, i = f"{base}-{i}", i + 1
    return k


def title_for(url, page):
    gh = GH_REPO.match(url)
    if gh:  # "grand_central_station" → "Grand Central Station README"
        return " ".join(w.capitalize() for w in re.split(r"[-_]+", gh.group(1))) + " README" * bool(gh.group(2))
    return re.split(r" [·|—–-] ", page.get("title", ""))[0][:40] or urlsplit(url).path.rsplit("/", 1)[-1]


def describe(k, e):
    """One line for the report."""
    if e["action"] == "add":
        return f"[{e['name']}]({e['href']}), new on the {e['line']} line as `{k}`"
    return f"{name(k)}, " + (f"edited ({e['change']})" if e["action"] == "edit" else f"gone ({e['reason']})")


def settled(entry, t):
    """Ready once its last deploy (or, if unknown, our first sighting) is SETTLE old."""
    return t - when(entry.get("deployed") or entry["seen"]) >= SETTLE


def render_proposed(entries):
    rows = [f'    "{k}": dict({", ".join(f"{f}={json.dumps(v, ensure_ascii=False)}" for f, v in e.items())}),\n'
            for k, e in entries.items()]
    return "{\n" + "".join(rows) + "}"


def replace_value(name_, text):
    """Rewrite the right-hand side of a top-level assignment in stations.py."""
    src = SOURCE.read_text()
    node = next(n.value for n in ast.parse(src).body
                if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == name_)
    starts = [0, *[i + 1 for i, ch in enumerate(src) if ch == "\n"]]
    a, b = starts[node.lineno - 1] + node.col_offset, starts[node.end_lineno - 1] + node.end_col_offset
    SOURCE.write_text(src[:a] + text + src[b:])


def rerun(*args, capture=False):
    """Run this script again in a fresh process, so it sees the file as edited."""
    r = subprocess.run([sys.executable, str(CLI), *args], check=True, text=True,
                       stdout=subprocess.PIPE if capture else sys.stderr)
    return r.stdout


def check():
    """Crawl every mapped page on my sites and list what the map should hear about:
    pages it doesn't have, linked since that page was last approved (on my
    sites, or my GitHub repos and READMEs, in whatever form), mapped
    pages edited since the last approval (links or content), and mapped pages
    that now 404. Each waits until its last deploy is SETTLE old, then goes into
    PROPOSED as "building" and is drawn. Waiting is recomputed from deploy times
    on every run, not stored, so the bot's own commits (which redeploy the home
    site) never restart a clock. An entry whose page reverts or disappears is
    withdrawn. Only PROPOSED changes; the graph itself changes through `apply`.

    --edits-only  just the edited-page part (the hourly run)
    --dry-run     report without writing (the public check)"""
    dry, edits_only, t = "--dry-run" in sys.argv, "--edits-only" in sys.argv, now()
    mapped = {norm(u) for s in STATIONS.values() for u in [s.get("href"), *s.get("also", [])] if u}
    todo = {norm(s["href"]): s["href"] for s in STATIONS.values()
            if s.get("href") and urlsplit(norm(s["href"])).netloc in MY_HOSTS}
    old = json.loads(LINKS.read_text())["pages"] if LINKS.exists() else {}
    pages = {}
    for u in sorted(todo):  # conditional GET: a 304 means "same as when you approved it"
        p = read(todo[u], old.get(u, {}).get("etag"))
        pages[u] = old[u] | dict(status=200) if p["status"] == 304 else p
    key_at = {norm(s["href"]): k for k, s in STATIONS.items() if s.get("href")}
    fresh = lambda **e: e | dict(seen=iso(t), stage="waiting", decision="pending")  # noqa: E731
    cand, notes = {}, []  # key → the entry this crawl says belongs in PROPOSED

    if not edits_only:  # pages the map doesn't have
        line_at = {norm(STATIONS[k]["href"]): ln["id"] for ln in LINES for sp in ln["spokes"] for k in sp[1]
                   if STATIONS[k].get("href")} | {norm(STATIONS["gc"]["href"]): "home"}
        order = [ln["id"] for ln in LINES if ln["id"] != "home"] + ["home"]  # home footers link everything
        known = {repo(u) for u in mapped | {norm(u) for u in IGNORE}}
        refs, first = {}, {}  # candidate (keyed by repo root for GitHub) → linking lines; the link as written
        for u, p in pages.items():
            if u not in old:
                continue  # no approved version to compare with yet; the next approval records one
            before = {x for sec in old[u]["links"].values() for x in sec}
            for x in sorted({x for sec in p["links"].values() for x in sec} - before):  # linked since approval
                mine = urlsplit(x).netloc in MY_HOSTS and not FILES.search(x)
                if (mine or GH_REPO.match(x)) and repo(x) not in known:
                    refs.setdefault(repo(x), set()).add(line_at.get(u, "home"))
                    first.setdefault(repo(x), x)
        href_key, taken = {repo(norm(e["href"])): k for k, e in PROPOSED.items() if "href" in e}, set(STATIONS) | set(PROPOSED)
        for r in sorted(refs):
            u = first[r]
            p = read(u)
            if p["status"] != 200 or not ("title" in p or GH_REPO.match(u)):
                continue  # broken links and files aren't stops; the build lists them
            k = href_key.get(r) or slug(u, taken)
            taken.add(k)
            cand[k] = fresh(action="add", name=title_for(u, p), href=u,
                            line=HOST_LINE.get(urlsplit(u).netloc) or min(refs[r], key=order.index),
                            deployed=p.get("modified") or (pushed(u) if GH_REPO.match(u) else "") or "")

    for u in sorted(set(pages) & set(old)):  # mapped pages edited since the last approval
        if pages[u]["status"] != 200 or (old[u].get("etag") and pages[u].get("etag") == old[u]["etag"]):
            continue  # gone, or the same version as approved
        la = {x for sec in old[u].get("links", {}).values() for x in sec}
        lb = {x for sec in pages[u]["links"].values() for x in sec}
        text = "hash" in old[u] and old[u]["hash"] != pages[u].get("hash")
        if la != lb or text:
            what = ", ".join(x for x in ((la != lb) * f"links +{len(lb - la)} −{len(la - lb)}", text * "content") if x)
            cand[key_at[u]] = fresh(action="edit", change=what, deployed=pages[u].get("modified", ""))

    if not edits_only:  # mapped pages that are gone
        for k, s in STATIONS.items():
            st = pages.get(norm(s["href"]), {}).get("status") if s.get("href") else None
            if st in (404, 410) and f"remove:{k}" not in IGNORE:
                cand[k] = fresh(action="remove", reason=f"HTTP {st}", deployed="")
            elif st not in (None, 200, 404, 410):
                notes.append(("Unreachable", f"{name(k)} (HTTP {st or 'no response'}); retrying next check"))

    nxt = {}
    for k, e in PROPOSED.items():  # what's already there, in its order
        if e["decision"] != "pending" or (edits_only and e["action"] != "edit"):
            nxt[k] = e  # decided entries belong to `apply`; others aren't this run's business
        elif k in cand:  # still true: keep its stage and first sighting, refresh the rest
            c = cand.pop(k)
            nxt[k] = e | {f: c[f] for f in ("name", "change", "deployed") if c.get(f)}
        else:
            reason = {"add": "no longer linked, or no longer live", "edit": "back to its approved version",
                      "remove": "back online"}[e["action"]]
            notes.append(("Withdrawn", f"{e.get('name') or name(k)}: {reason}"))
    nxt |= {k: c for k, c in cand.items() if k not in nxt}  # newly found; never over a decided entry

    keep = {}
    for k, e in nxt.items():  # the lazy step: settle, then draw
        if e["decision"] == "pending" and e["stage"] == "waiting":
            if settled(e, t):
                e = e | dict(stage="building")
                notes.append(("Now under construction on the map", describe(k, e)))
            else:
                ready = when(e.get("deployed") or e["seen"]) + SETTLE
                notes.append(("Waiting to settle", f"{describe(k, e)}; drawn at the first check after {pt(ready)}"))
        if e["stage"] == "building" or e["decision"] != "pending" or not e.get("deployed"):
            keep[k] = e  # waiting with a known deploy time is recomputed next run instead

    print(f"## {'Live check' if dry else 'Map check'}{' (edits)' * edits_only}, {pt(t)}\n")
    for group in ("Now under construction on the map", "Waiting to settle", "Withdrawn", "Unreachable"):
        items = [x for g, x in notes if g == group]
        if items:
            print(f"**{group}**\n" + "".join(f"- {x}\n" for x in items))
    if not notes:
        print("No changes: the map matches the live sites.")
    if dry or keep == PROPOSED:
        return
    replace_value("PROPOSED", render_proposed(keep))
    rerun()
    if any(e["stage"] == "building" and e["decision"] == "pending" for e in keep.values()):
        print('To approve, change `decision="pending"` to `"yes"` in `tools/gcmap/stations.py` on main '
              '(or `"no"` for a new or gone page). That opens a pull request with the full redraw.')


def apply():
    """Approval, run on its own branch: carry out every yes/no in PROPOSED by
    editing stations.py, re-crawl every page, recompute every shortest
    path, stamp the update notice, verify, and print the pull request report."""
    decided = {k: p for k, p in PROPOSED.items() if p["decision"] in ("yes", "no")}
    if not decided and "--refresh" not in sys.argv:
        print("Nothing to apply: no decisions in PROPOSED.")
        return
    before = json.loads(rerun("stats", capture=True))
    src = SOURCE.read_text()
    starts = [0, *[i + 1 for i, ch in enumerate(src) if ch == "\n"]]  # offset of each line
    top = {n.targets[0].id: n.value for n in ast.parse(src).body   # STATIONS, LINES, ... as syntax nodes
           if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    edits = []  # (start, end, text), applied back to front

    def off(node, end=False):  # a syntax node's position in src
        return starts[(node.end_lineno if end else node.lineno) - 1] + (node.end_col_offset if end else node.col_offset)

    def spoke_lists():  # every spoke's list of stop keys, as (line id, list node)
        for call in top["LINES"].elts:
            kw = {k.arg: k.value for k in call.keywords}
            for sp in kw["spokes"].elts:
                yield kw["id"].value, sp.elts[1]

    def drop_entry(d, k):  # a whole "key": value line (or lines) from a dict
        i = [x.value for x in d.keys].index(k)
        edits.append((starts[d.keys[i].lineno - 1], starts[d.values[i].end_lineno], ""))

    def drop_item(seq, k):  # one item from a list or set, with its comma
        items = seq.elts
        i = [x.value for x in items].index(k)
        a, b = items[i], items[i + 1] if i + 1 < len(items) else None
        if b:
            edits.append((off(a), off(b), ""))
        elif i:
            edits.append((off(items[i - 1], end=True), off(a, end=True), ""))

    def before_close(node, text):  # a new line just above a closing bracket on its own line
        edits.append((starts[node.end_lineno - 1], starts[node.end_lineno - 1], text))

    done, summary = [], []
    for k, p in decided.items():
        drop_entry(top["PROPOSED"], k)
        if p["action"] == "add" and p["decision"] == "yes":
            before_close(top["STATIONS"], f'    "{k}": dict(name={json.dumps(p["name"], ensure_ascii=False)}, href="{p["href"]}"),\n')
            keys = next(lst for line, lst in spoke_lists() if line == p["line"]).elts  # the line's first spoke
            planned = [x for x in keys if STATIONS[x.value].get("status") == "planned"]
            if planned:  # new stops go ahead of planned ones
                edits.append((off(planned[0]), off(planned[0]), f'"{k}", '))
            else:
                edits.append((off(keys[-1], end=True), off(keys[-1], end=True), f', "{k}"'))
            done.append(f"Added {p['name']} (`{k}`) to the {p['line']} line")
            summary.append(f"added {p['name']}")
        elif p["action"] == "edit":  # the re-crawl below picks the edit up; "no" just clears it for now
            done.append(f"Re-checked {name(k)} after your edits ({p['change']})" if p["decision"] == "yes"
                        else f"Cleared the edit marker on {name(k)}; the next check proposes it again if it still differs")
            if p["decision"] == "yes":
                summary.append(f"updated {name(k)}")
        elif p["action"] == "remove" and p["decision"] == "yes":
            drop_entry(top["STATIONS"], k)
            for _, lst in spoke_lists():
                if k in [x.value for x in lst.elts]:
                    drop_item(lst, k)
            if k in HUBS:
                drop_item(top["HUBS"], k)
            done.append(f"Removed {name(k)} (`{k}`)")
            summary.append(f"removed {name(k)}")
        else:
            before_close(top["IGNORE"], f'    "{p["href"] if p["action"] == "add" else "remove:" + k}",\n')
            done.append(f"Declined {p.get('name') or name(k)} (`{k}`); it won't be proposed again")
    for a, b, text in sorted(edits, reverse=True):
        src = src[:a] + text + src[b:]
    SOURCE.write_text(src)
    note = "; ".join(summary) or "links refreshed"
    note = note[0].upper() + note[1:]
    replace_value("UPDATE", f"dict(at={json.dumps(iso(now()))}, note={json.dumps(note, ensure_ascii=False)})")

    rerun("crawl")                                  # every page's links, as they are now
    after = json.loads(rerun("stats", capture=True))
    rerun("verify")                                 # renders twice; both must match
    print(f"## Map update: {note}\n")
    print("".join(f"- {d}\n" for d in done) or "- No decisions; links re-crawled and every path recomputed.\n")
    print(impact(before, after))


def verify():
    """Every stop on exactly one line, no duplicate pages, well-formed PROPOSED,
    and two renders write the same file."""
    problems = []
    placed = [k for _, _, keys, _ in spokes() for k in keys]
    problems += [f"{k} is on more than one line" for k in sorted({k for k in placed if placed.count(k) > 1})]
    problems += [f"{k} is on a line but not in STATIONS" for k in placed if k not in STATIONS]
    problems += [f"{k} is in STATIONS but on no line" for k in STATIONS if k != "gc" and k not in placed]
    problems += [f"HUBS names {k}, which isn't a stop" for k in HUBS - set(STATIONS)]
    hrefs = [norm(s["href"]) for s in STATIONS.values() if s.get("href")]
    problems += [f"{u} is two stops" for u in sorted({u for u in hrefs if hrefs.count(u) > 1})]
    for k, p in PROPOSED.items():
        if p.get("decision") not in ("pending", "yes", "no") or p.get("stage") not in ("waiting", "building"):
            problems.append(f"PROPOSED {k}: decision must be pending/yes/no and stage waiting/building")
        if p.get("action") == "add" and p.get("line") not in {ln["id"] for ln in LINES}:
            problems.append(f"PROPOSED {k}: unknown line {p.get('line')!r}")
    rerun()
    first = hashlib.sha256(PAGE.read_bytes()).digest()
    rerun()
    if hashlib.sha256(PAGE.read_bytes()).digest() != first:
        problems.append("two renders wrote different files")
    print("\n".join(f"  ! {p}" for p in problems) or "Verified: map is consistent and renders are reproducible.")
    sys.exit(1 if problems else 0)
