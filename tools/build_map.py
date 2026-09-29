#!/usr/bin/env python3
"""Grand Central map: command-line entry point.

    python3 tools/build_map.py                  render index.html from stations.py and links.json
    python3 tools/build_map.py check            crawl; draw new, edited and gone pages once settled
    python3 tools/build_map.py check --edits-only   the hourly run: edited pages only
    python3 tools/build_map.py check --dry-run  report only; writes nothing (the public check)
    python3 tools/build_map.py apply            carry out yes/no decisions, re-crawl, recompute
    python3 tools/build_map.py apply --refresh  re-crawl and recompute with no decisions
    python3 tools/build_map.py verify           integrity checks; two renders must be byte-identical
    python3 tools/build_map.py crawl            record every mapped page's links (used by apply)
    python3 tools/build_map.py stats            the graph as JSON (used by apply's report)

The map's data lives in tools/gcmap/stations.py; see README.md for the design.
"""
import json
import sys

from gcmap import crawl, graph, pipeline, render

COMMANDS = {
    "check": pipeline.check,
    "apply": pipeline.apply,
    "verify": pipeline.verify,
    "crawl": crawl.crawl,
    "stats": lambda: print(json.dumps(graph.stats())),
}

if __name__ == "__main__":
    COMMANDS.get(sys.argv[1] if sys.argv[1:] else "", render.build)()
