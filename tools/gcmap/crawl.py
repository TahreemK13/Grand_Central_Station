"""HTTP and HTML: fetch pages (conditionally), extract links, and give every URL
one canonical identity so a page always compares equal to itself."""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from .clock import iso, now, when
from .settings import ALIASES, GH_REPO, LINKS, MY_HOSTS
from .stations import H, STATIONS


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


def repo(url):
    """A repo's root, #readme and README file are one stop: key them by the root."""
    m = GH_REPO.match(url)
    return f"https://github.com/tahreemk13/{m.group(1)}" if m else url


class Anchors(HTMLParser):
    """Every <a href>, tagged with the nav/header/footer it sits in (else body)."""
    SECTIONS = ("nav", "header", "footer")

    def __init__(self):
        super().__init__()
        self.stack, self.found, self.title, self.in_title, self.h1, self.in_h1 = [], [], "", False, "", False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_h1:
            self.h1 += data

    def handle_starttag(self, tag, attrs):
        self.in_title = tag == "title" and not self.title
        self.in_h1 = self.in_h1 or (tag == "h1" and not self.h1)
        if tag in self.SECTIONS:
            self.stack.append(tag)
        href = dict(attrs).get("href") if tag == "a" else None
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            self.found.append((self.stack[-1] if self.stack else "body", href))

    def handle_endtag(self, tag):
        self.in_title = False
        self.in_h1 = self.in_h1 and tag != "h1"
        if tag in self.stack:
            while self.stack.pop() != tag:
                pass


GENERATED = re.compile(r"<!-- (MAP|DIR|STATUS):START.*?<!-- \1:END -->", re.S)  # this page's own output


def extract(html, page_url):
    """(links by section, the page's header: its first <h1>, else its <title>)."""
    html = GENERATED.sub("", html)
    parser = Anchors()
    parser.feed(html)
    links = {}
    for section, href in parser.found:
        url = norm(href, page_url)
        if url and url not in links.setdefault(section, []):
            links[section].append(url)
    return links, " ".join((parser.h1 if parser.h1.strip() else parser.title).split())


def fetch(url, headers=None):
    """(HTTP status, final URL, body text or None if it isn't HTML/JSON, response headers)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "grand-central-map", **(headers or {})})
        with urllib.request.urlopen(req, timeout=20) as r:
            text = re.search(r"html|json", r.headers.get("Content-Type", ""))
            return r.status, r.url, r.read().decode("utf-8", "replace") if text else None, r.headers
    except urllib.error.HTTPError as e:  # includes 304 Not Modified
        return e.code, url, None, {}
    except OSError:
        return 0, url, None, {}


def read(url, etag=None):
    """One page: status; title, links and a content fingerprint if it's HTML; its
    ETag; and when it was last deployed. With the ETag from last time, an
    unchanged page answers 304 with no body, so nothing is downloaded or parsed."""
    status, final, html, headers = fetch(url, {"If-None-Match": etag} if etag else None)
    page = dict(status=status, links={})
    if html is not None:
        page["links"], page["title"] = extract(html, final)
        page["hash"] = hashlib.sha256(" ".join(GENERATED.sub("", html).split()).encode()).hexdigest()[:16]
    if headers.get("ETag"):
        page["etag"] = headers["ETag"]
    if headers.get("Last-Modified"):
        page["modified"] = iso(parsedate_to_datetime(headers["Last-Modified"]))
    return page


def pushed(url):
    """When a GitHub repo was last pushed to (its deploy time), or None."""
    token = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}"} if os.environ.get("GH_TOKEN") else {}
    status, _, body, _ = fetch(f"https://api.github.com/repos/tahreemk13/{GH_REPO.match(url).group(1)}", token)
    return iso(when(json.loads(body)["pushed_at"])) if status == 200 and body else None


def crawl():
    """Record every mapped page's links in links.json. Run by `apply`."""
    todo = {norm(s["href"]): s["href"] for s in STATIONS.values()
            if s.get("href") and urlsplit(norm(s["href"])).netloc in MY_HOSTS}
    pages = {}
    for u in sorted(todo):
        p = read(todo[u])
        p.pop("modified", None)  # deploy times change on every deploy; the ETag is the version
        pages[u] = p
    LINKS.write_text(json.dumps(dict(crawled=str(now().date()), pages=pages), indent=1) + "\n")
