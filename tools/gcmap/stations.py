"""The map's data: the only module you edit by hand.

STATIONS   what each stop is      name, href, optional note / status / also
LINES      where stops sit        a compass spoke per line; order within a ring
PROPOSED   the pipeline's queue   written by `check`; you change only `decision`
IGNORE     pages you declined     never proposed again
UPDATE     the last approval      stamped by `apply`, shown under the map

`apply` edits this file's source (via its syntax tree) when you approve a
change, so keep one entry per line in PROPOSED and IGNORE.
"""
H = "https://www.tahreemkarim.xyz"
G = "https://garden.tahreemkarim.xyz"
R = "https://risingtigers.tahreemkarim.xyz"
P = "https://github.com/TahreemK13/portfolio"

# Optional: an ntfy.sh topic. When a visitor's "check for new pages" finds one,
# your phone gets a push (install the ntfy app, subscribe to this topic). Pick
# something unguessable: the topic is visible in the page source. "" turns it off.
NOTIFY_TOPIC = ""

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
HOST_LINE = {"www.tahreemkarim.xyz": "home", "garden.tahreemkarim.xyz": "garden",
             "risingtigers.tahreemkarim.xyz": "tigers", "portfolio.tahreemkarim.xyz": "portfolio"}

# Written by `check`, one line per page. The only field to edit by hand is
# decision: change "pending" to "yes" or "no" and push to main. That opens the
# approval pull request. stage is "waiting" (settling, not drawn) or "building"
# (drawn as an under-construction stop, or struck through if the page is gone).
PROPOSED = {
}

IGNORE = [  # pages you said no to: never proposed again
]

# Stamped by `apply`; shown under the map as "Map updated …".
UPDATE = dict(at="", note="")


def name(k):
    """A stop's label on one line."""
    return STATIONS[k]["name"].replace("\n", " ")
