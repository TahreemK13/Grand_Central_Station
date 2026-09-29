"""gcmap: the Grand Central system map.

A static-site generator for one SVG subway map, plus the pipeline that keeps it
true to the live sites. Modules, in dependency order:

    settings   tunables: hosts, settle window, geometry
    stations   the data you edit: stops, lines, the approval queue
    clock      UTC storage, Pacific display, GC_NOW for tests
    crawl      conditional HTTP, link extraction, canonical URLs
    graph      BFS click distance, Brandes edge betweenness, impact report
    render     layout, SVG, directory, status block, index.html splicing
    pipeline   check → settle → draw → approve → apply → verify

Entry point: tools/build_map.py.
"""
