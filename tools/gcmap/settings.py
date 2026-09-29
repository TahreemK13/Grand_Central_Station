"""Tunables: which hosts count as mine, the settle window, and map geometry."""
import re
from datetime import timedelta
from math import sqrt
from pathlib import Path
from zoneinfo import ZoneInfo

# ---- files
ROOT = Path(__file__).resolve().parents[2]
PAGE = ROOT / "index.html"            # the hub page the map is rendered into
LINKS = ROOT / "tools" / "links.json"  # link snapshot as of the last approval
CLI = ROOT / "tools" / "build_map.py"

# ---- what counts as mine
MY_HOSTS = {"www.tahreemkarim.xyz", "garden.tahreemkarim.xyz",
            "portfolio.tahreemkarim.xyz", "risingtigers.tahreemkarim.xyz"}
ALIASES = {"https://tahreemk13.github.io/portfolio": "https://portfolio.tahreemkarim.xyz"}  # old URL, redirects
GH_REPO = re.compile(r"^https://github\.com/tahreemk13/([^/]+)(/blob/[^/]+/readme\.md)?$")  # my repos, their READMEs
FILES = re.compile(r"\.(pdf|png|jpe?g|gif|svg|webp|zip|csv|json|txt|xml|ipynb)$", re.I)  # links that aren't pages

# ---- pipeline
SETTLE = timedelta(hours=24)  # a change is drawn once its last deploy is this old
PACIFIC = ZoneInfo("America/Los_Angeles")

# ---- geometry (SVG user units)
CX, CY = 700, 520                  # Grand Central
AX, AY = 640, 440                  # outer ring radius, horizontal and vertical
RINGS = [0.12, 0.56, 0.90, 1.00]   # ring edges: 1 click | 2+ clicks | planned
HALF = (700, 490)                  # half-width and half-height of the frame around Grand Central
VIEW = f"{CX - HALF[0]} {CY - HALF[1]} {2 * HALF[0]} {2 * HALF[1]}"  # centered on the hub
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0), "SE": (1, 1), "SW": (-1, 1)}
DIAG = AX * AY / sqrt(AX * AX + AY * AY)  # where a 45° spoke meets each ring
