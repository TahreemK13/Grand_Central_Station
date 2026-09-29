"""A stand-in for the web, loaded into every process the pipeline starts.

Python imports sitecustomize at startup when it's on PYTHONPATH, so pointing
PYTHONPATH here swaps urllib's urlopen for one that serves $GC_FIXTURES, a JSON
file of {url: {"status", "body", "modified", "type"}}. It answers the way GitHub
Pages does: ETags, 304 Not Modified for If-None-Match, Last-Modified. Status 0
simulates an unreachable site. Every request is logged to $GC_WEBLOG.
"""
import hashlib
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from email.message import Message
from email.utils import format_datetime


def _open(req, timeout=None):
    from gcmap.crawl import norm  # the pipeline's own URL identity
    url = req.full_url
    pages = json.load(open(os.environ["GC_FIXTURES"]))
    page = pages.get(url) or pages.get(norm(url) or "") or {"status": 404, "body": ""}
    etag = '"' + hashlib.sha1(page["body"].encode()).hexdigest()[:12] + '"'
    status = 304 if page["status"] == 200 and req.get_header("If-none-match") == etag else page["status"]
    with open(os.environ["GC_WEBLOG"], "a") as log:
        log.write(f"{status} {url}\n")
    if status == 0:
        raise urllib.error.URLError("unreachable")
    if status != 200:
        raise urllib.error.HTTPError(url, status, "", {}, None)
    headers = Message()
    headers["Content-Type"] = page.get("type", "text/html")
    headers["ETag"] = etag
    if page.get("modified"):
        headers["Last-Modified"] = format_datetime(datetime.fromisoformat(page["modified"].replace("Z", "+00:00")), usegmt=True)

    class Response:
        status, url, headers = 200, req.full_url, None

        def read(self):
            return page["body"].encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    response = Response()
    response.headers = headers
    return response


urllib.request.urlopen = _open
