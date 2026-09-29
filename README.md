# Grand Central Station

The source for **[www.tahreemkarim.xyz](https://www.tahreemkarim.xyz)**, the home page that connects everything else: the [digital garden](https://garden.tahreemkarim.xyz), the [portfolio](https://portfolio.tahreemkarim.xyz), and the [Rising Tigers Initiative](https://risingtigers.tahreemkarim.xyz).

It's plain HTML served by GitHub Pages. There's no framework, no build step for the pages, and no dependencies beyond Python 3.9+ for the map script.

## What's in here

| Path | What it is |
| --- | --- |
| `index.html` | Grand Central: the home page, including the system map |
| `now.html`, `science.html`, `free-resources.html`, `art.html`, `travel.html` | The other Home line pages |
| `images/` | Photos and the social card |
| `tools/build_map.py` | Draws the system map from real links |
| `tools/links.json` | Every link found on every mapped page |
| `CNAME` | The custom domain for GitHub Pages |
| `SETUP.md` | One-time setup: repo, Pages, DNS |

Each page carries its own CSS in a `<style>` block, with the design tokens (colors, fonts, spacing) at the top.

## The system map

The map on the home page is drawn like a subway map, but every part of it comes from the links actually on your pages, footers included.

- **Lines** are sites. Home runs west, Garden north, Rising Tigers east, Portfolio south, and your profiles sit on two short shuttle spurs.
- **Rings** are clicks. A stop's ring is the fewest clicks it takes to reach that page from Grand Central.
- **Connectors** are the links between pages. The more shortest routes run through a link, the thicker it's drawn.
- **Bullets** under a stop show which other lines that page links to.

Hover any stop to see its shortest route from here.

### Updating it

```bash
python3 tools/build_map.py crawl   # re-read every page's links into tools/links.json
python3 tools/build_map.py         # redraw the map and directory in index.html
```

Run `crawl` after you change links on any of the sites, then rebuild and commit both files. The build only touches the parts of `index.html` between the `MAP:` and `DIR:` markers, so edit the rest of the page freely. The same links always produce the same file, so a diff only shows real changes.

The build also flags problems:

- `!` means a stop nothing links to, or a page that didn't load.
- `·` means a link to one of your pages that isn't on the map yet, often a typo.

### Adding or changing a stop

Everything you'd edit sits at the top of `tools/build_map.py`.

**`STATIONS`** says what each stop is:

```python
"lib": dict(name="Library", href=f"{G}/library"),
"art": dict(name="Art", href=f"{H}/art", status="building", note="Soon"),
"bang": dict(name="Bangladesh", status="planned"),  # no href yet
```

The optional fields are `note` (a small caption), `status` (`building` or `planned`), and `also` (extra URLs that count as this stop).

**`LINES`** says which line a stop rides and in what order:

```python
dict(id="garden", letter="G", name="Garden line", domain="garden.tahreemkarim.xyz",
     spokes=[("N", ["gdn", "lib", "brain", "cur", "born", "mvd", "scicomm"])]),
```

You never type coordinates. Add the key to a line, run the build, and the stop lands in the right ring.

### How it works

1. **Crawl.** Every `<a href>` on each page is recorded by section (nav, header, body, footer). URLs are normalized so one page always matches itself.
2. **Rings.** A breadth-first search from Grand Central gives each page its click distance.
3. **Connectors.** The same search runs from every page to every other page. Each link is weighted by its share of those shortest routes, a measure called edge betweenness. [Brandes' algorithm](https://snap.stanford.edu/class/cs224w-readings/brandes01centrality.pdf) computes it with one search per page instead of checking every pair.

Grand Central's own links aren't drawn as connectors, because the rings already show them.

## Publishing

Push to `main` and GitHub Pages deploys in a minute or two. For first-time setup (the repo, Pages, DNS, HTTPS), see [`SETUP.md`](SETUP.md).
