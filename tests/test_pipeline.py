#!/usr/bin/env python3
"""Lifecycle scenarios for the map pipeline, against a simulated web and clock.

    python3 tests/test_pipeline.py        (or: python3 -m unittest discover tests)

Each test copies the repo to a temporary folder, serves the sites from a fake
web built from the approved snapshot (tests/fakeweb), approves that baseline,
then changes the web and moves the clock (GC_NOW) the way real use would.
Offline and self-contained: no network, no dependencies beyond the standard library.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PF, G, H = "https://portfolio.tahreemkarim.xyz", "https://garden.tahreemkarim.xyz", "https://www.tahreemkarim.xyz"
REPO_LINK = "https://github.com/TahreemK13/Grand_Central_Station#readme"
T0 = "2026-09-28T19:00Z"      # baseline approval
DEPLOY = "2026-10-05T17:00Z"  # Monday 10:00 am PDT


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT, self.dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", ".preview"))
        data = self.dir / "tools/gcmap/stations.py"  # start every scenario with an empty queue,
        data.write_text(re.sub(r"PROPOSED = \{\n.*?\n\}", "PROPOSED = {\n}", data.read_text(), count=1, flags=re.S))
        self.web_file, self.log = self.dir / "web.json", self.dir / "web.log"  # whatever is queued in the real repo
        snapshot = json.loads((self.dir / "tools/links.json").read_text())["pages"]
        self.web = {u: dict(status=200, modified="2026-09-20T18:00Z", body=self.html(p)) for u, p in snapshot.items()}
        self.save()
        self.run_at(T0, "apply", "--refresh")  # the first approval records ETags and fingerprints

    def tearDown(self):
        shutil.rmtree(self.dir)

    # ---- the simulated world
    @staticmethod
    def html(page, extra=""):
        sections = "".join(f"<{s}>" + "".join(f'<a href="{u}">x</a>' for u in links) + f"</{s}>"
                           for s, links in page["links"].items())
        return f"<html><head><title>{page.get('title', '')}</title></head><body>{sections}{extra}</body></html>"

    def save(self):
        self.web_file.write_text(json.dumps(self.web))

    def deploy(self, host, at):  # GitHub Pages stamps the whole site on each deploy
        for url, page in self.web.items():
            if url.startswith(host):
                page["modified"] = at
        self.save()

    def link(self, page, href, at=DEPLOY):
        self.web[page]["body"] = self.web[page]["body"].replace("</body>", f'<a href="{href}">new</a></body>')
        self.deploy(page, at)

    def run_at(self, at, *args):
        env = dict(os.environ, GC_NOW=at, GC_FIXTURES=str(self.web_file), GC_WEBLOG=str(self.log),
                   PYTHONPATH=f"{ROOT / 'tests/fakeweb'}:{self.dir / 'tools'}")
        r = subprocess.run([sys.executable, "-B", str(self.dir / "tools/build_map.py"), *args],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stdout

    def stations(self):
        return (self.dir / "tools/gcmap/stations.py").read_text()

    def proposed(self):
        return re.search(r"PROPOSED = \{\n(.*?)\}", self.stations(), re.S).group(1)

    def decide(self, word):
        path = self.dir / "tools/gcmap/stations.py"
        path.write_text(path.read_text().replace('decision="pending"', f'decision="{word}"'))

    def add_repo_and_readme(self):
        self.web["https://github.com/tahreemk13/grand_central_station"] = dict(status=200, body="<title>repo</title>")
        self.web["https://api.github.com/repos/tahreemk13/grand_central_station"] = dict(
            status=200, type="application/json", body=json.dumps(dict(pushed_at="2026-10-05T16:30:00Z")))
        self.link(PF, REPO_LINK)

    # ---- scenarios
    def test_quiet_check_costs_only_304s(self):
        self.log.write_text("")
        self.assertIn("No changes", self.run_at("2026-10-01T18:00Z", "check"))
        statuses = {line.split()[0] for line in self.log.read_text().splitlines()}
        self.assertEqual(statuses, {"304"}, "an unchanged site should cost only 304s")

    def test_edit_waits_a_day_then_turns_orange(self):
        self.link(PF, f"{PF}/extra-section")
        before = self.stations()
        self.assertIn("Waiting to settle", self.run_at("2026-10-05T18:00Z", "check", "--edits-only"))
        self.assertEqual(self.stations(), before, "nothing is written while a change settles")
        self.assertIn("Now under construction", self.run_at("2026-10-06T17:30Z", "check", "--edits-only"))
        self.assertIn('"pf": dict(action="edit"', self.proposed())
        self.assertIn('class="net-line edit"', (self.dir / "index.html").read_text())

    def test_churn_never_reaches_the_map(self):
        draft = f"{G}/posts/draft"
        self.web[draft] = dict(status=200, body="<title>Draft</title>", modified="2026-10-05T17:30Z")
        self.link(G, draft + ".html", at="2026-10-05T17:30Z")
        self.run_at("2026-10-05T18:00Z", "check")
        self.web[G]["body"] = self.web[G]["body"].replace(f'<a href="{draft}.html">new</a>', "")
        del self.web[draft]
        self.deploy(G, "2026-10-05T20:00Z")
        self.run_at("2026-10-07T18:00Z", "check")
        self.assertEqual(self.proposed(), "", "a page published and pulled before settling never lands")

    def test_new_page_by_any_link_form_waits_outside_the_math(self):
        self.add_repo_and_readme()  # the home footer already links this repo; the new link is on the portfolio
        self.assertIn("Waiting to settle", self.run_at("2026-10-05T18:00Z", "check"))
        self.assertIn("Now under construction", self.run_at("2026-10-06T18:00Z", "check"))
        self.assertIn('"grand-central-station": dict(action="add", name="Grand Central Station"', self.proposed())
        self.assertIn('line="portfolio"', self.proposed())
        stop = re.search(r'<a [^>]*data-k="grand-central-station"[^>]*>', (self.dir / "index.html").read_text()).group(0)
        self.assertNotIn("data-route", stop, "an unapproved stop has no shortest path yet")

    def test_approval_integrates_recomputes_and_stamps(self):
        self.add_repo_and_readme()
        self.run_at("2026-10-06T18:00Z", "check")
        self.decide("yes")
        report = self.run_at("2026-10-06T20:14Z", "apply")
        self.assertIn("Effect on shortest paths", report)
        self.assertIn("**Joins**", report)
        src = self.stations()
        self.assertIn('"grand-central-station": dict(name="Grand Central Station"', src)
        self.assertRegex(src, r'"pres", "grand-central-station"\]')
        self.assertIn('UPDATE = dict(at="2026-10-06T20:14Z"', src)
        self.assertEqual(self.proposed(), "")
        self.assertIn("Map updated", (self.dir / "index.html").read_text())
        self.assertIn("No changes", self.run_at("2026-10-07T18:00Z", "check"))

    def test_decline_is_remembered(self):
        self.add_repo_and_readme()
        self.run_at("2026-10-06T18:00Z", "check")
        self.decide("no")
        self.run_at("2026-10-06T20:00Z", "apply")
        self.assertIn('"https://github.com/tahreemk13/grand_central_station",', self.stations())
        self.run_at("2026-10-08T18:00Z", "check")
        self.assertNotIn("grand-central-station", self.proposed())

    def test_gone_page_is_marked_then_removed_on_yes(self):
        self.web[f"{H}/art"]["status"] = 404
        self.save()
        self.run_at("2026-10-05T18:00Z", "check")
        self.assertIn('stage="waiting"', self.proposed(), "no deploy time for a 404: first sighting is stored")
        self.run_at("2026-10-06T18:30Z", "check")
        self.assertIn('"art": dict(action="remove"', self.proposed())
        self.assertIn('stage="building"', self.proposed())
        self.decide("yes")
        self.run_at("2026-10-06T19:00Z", "apply")
        self.assertNotIn('"art":', self.stations())
        self.assertNotIn('"art"', re.search(r"LINES = \[.*?\n\]", self.stations(), re.S).group(0))

    def test_outage_is_not_deletion(self):
        for page in self.web.values():
            page["status"] = 0
        self.save()
        before = self.stations()
        self.assertIn("Unreachable", self.run_at("2026-10-05T18:00Z", "check"))
        self.assertEqual(self.stations(), before, "an unreachable site proposes nothing")

    def test_dry_run_writes_nothing(self):
        self.add_repo_and_readme()
        files = {p: p.read_bytes() for p in self.dir.rglob("*") if p.is_file() and p.name != "web.log"}
        self.assertIn("Grand Central Station", self.run_at("2026-10-06T18:00Z", "check", "--dry-run"))
        self.assertEqual({p: p.read_bytes() for p in files}, files)

    def test_decided_entries_are_left_for_apply(self):
        self.add_repo_and_readme()
        self.run_at("2026-10-06T18:00Z", "check")
        self.decide("yes")
        decided = self.proposed()
        self.run_at("2026-10-06T19:00Z", "check")
        self.assertEqual(self.proposed(), decided)

    def test_first_run_without_a_snapshot(self):
        (self.dir / "tools/links.json").unlink()
        self.assertNotIn("Traceback", self.run_at("2026-10-05T18:00Z", "check"))
        self.run_at("2026-10-05T18:00Z")  # renders without a snapshot too


if __name__ == "__main__":
    unittest.main(verbosity=2)
