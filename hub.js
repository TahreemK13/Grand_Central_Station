// Grand Central hub: the menu, the system map (centering, reveal, route tracing,
// hover highlights) and the live check under it. Loaded at the end of index.html.

// Menu toggle: one button, no scroll listeners.
(() => {
  const btn = document.querySelector('.menu-btn');
  const menu = document.getElementById('site-menu');
  const set = (open) => {
    btn.setAttribute('aria-expanded', open);
    menu.classList.toggle('open', open);
    if (open) menu.querySelector('a').focus({ preventScroll: true });
  };
  btn.addEventListener('click', () => set(btn.getAttribute('aria-expanded') !== 'true'));
  menu.addEventListener('click', (e) => { if (e.target.closest('a')) set(false); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menu.classList.contains('open')) { set(false); btn.focus(); }
  });
  document.addEventListener('click', (e) => {
    if (menu.classList.contains('open') && !menu.contains(e.target) && !btn.contains(e.target)) set(false);
  });
})();

// System map: opens centered on Grand Central, reveals once, traces routes, highlights on hover.
(() => {
  const svg = document.querySelector('svg.net');
  if (!svg) return;
  const sc = svg.parentElement;

  // The frame is symmetric about the hub, so the middle of the scroll area is Grand Central.
  // Re-center on resize and whenever the map comes into view (Safari can settle its width late),
  // until the visitor scrolls it themselves.
  let moved = false;
  ['pointerdown', 'wheel', 'keydown', 'touchstart'].forEach((t) => sc.addEventListener(t, () => { moved = true; }, { once: true, passive: true }));
  const center = () => { if (!moved) sc.scrollLeft = (sc.scrollWidth - sc.clientWidth) / 2; };
  new ResizeObserver(center).observe(sc);
  if ('IntersectionObserver' in window) new IntersectionObserver(([e]) => { if (e.isIntersecting) center(); }).observe(sc);

  // One reveal, outward from the hub, when Grand Central reaches the middle of the screen,
  // so it plays where the reader is looking. A fast fling past the hub triggers it too.
  // Skipped for reduced motion; without script the map is simply there.
  const hub = svg.querySelector('[data-k=gc]');
  if (hub && !matchMedia('(prefers-reduced-motion: reduce)').matches && 'IntersectionObserver' in window) {
    let io, below = false, ticking = false;
    const go = () => {
      svg.classList.replace('pre', 'go');
      io.disconnect();
      removeEventListener('scroll', onScroll);
    };
    // A fling can carry the hub past the middle band, or stop with it near the top,
    // without the observer ever reporting it. While the reveal is pending, a passive
    // scroll check (at most once per frame) covers that, then removes itself.
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        ticking = false;
        const r = hub.getBoundingClientRect(), mid = r.top + r.height / 2;
        if (r.top > innerHeight) below = true;                // coming up from below the screen
        else if (below && mid < innerHeight * .75) go();      // reached or passed the band, however fast
      });
    };
    svg.classList.add('pre');
    io = new IntersectionObserver(([e]) => { if (e.isIntersecting) go(); }, { rootMargin: '-25% 0px -35% 0px' });
    io.observe(hub);
    addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    addEventListener('beforeprint', go);
  }

  // Trace the shortest route to whatever is hovered or focused.
  const NS = 'http://www.w3.org/2000/svg', line = document.createElementNS(NS, 'polyline');
  const pos = {}, stop = {};
  line.setAttribute('class', 'trace');
  svg.querySelectorAll('[data-k]').forEach((el) => { stop[el.dataset.k] = el; });
  svg.querySelectorAll('.hit').forEach((c) => { pos[c.parentNode.dataset.k] = c.getAttribute('cx') + ',' + c.getAttribute('cy'); });
  let lit = [];
  const clear = () => {
    lit.forEach((el) => el.classList.remove('on'));
    lit = [];
    line.remove();
    svg.classList.remove('tracing');
  };
  const show = (a) => {
    clear();
    const route = a.dataset.route.split(' ');
    line.setAttribute('points', route.map((k) => pos[k]).join(' '));
    svg.insertBefore(line, svg.querySelector('[data-k]'));
    lit = route.map((k) => stop[k]);
    lit.forEach((el) => el.classList.add('on'));
    svg.classList.add('tracing');
  };
  let anchor = null;  // pointer position while a dwelled label is levelled (see the dwell section below)
  const on = (e) => {
    if (anchor) return;  // a levelled label has moved: what is under the pointer means nothing
    const a = e.target.closest('[data-route]');
    if (a) show(a); else clear();
  };
  svg.addEventListener('pointerover', on);
  svg.addEventListener('focusin', on);
  svg.addEventListener('pointerleave', clear);
  svg.addEventListener('focusout', clear);

  // ---- Hover highlights (pointer only; CSS does the drawing, this only sets classes).
  // pointermove can fire at 1000 Hz, so its handler only records the pointer and asks for
  // one frame of work; nothing here allocates per move or runs at page load.
  const STOP = 'a[data-k], .st-planned';
  const at = { x: 0, y: 0, on: false };  // the pointer, reused

  // Label hit pads. Hover grows a label about its stop end, and the gaps between its words and
  // badges let that growth slide them off a resting pointer: hover drops, the label shrinks back
  // under the pointer, and it jiggles (worst on a ring, whose hit band then catches the pointer).
  // One transparent rect behind each label covers its whole extent, pivot included, so growing
  // only ever widens what is under the pointer. Sized by the browser on first entry, not at load.
  svg.addEventListener('pointerenter', () => {
    svg.querySelectorAll('.lbl').forEach((g) => {
      const b = g.getBBox(), r = document.createElementNS(NS, 'rect');
      r.setAttribute('class', 'lbl-hit');
      r.setAttribute('x', b.x - 2); r.setAttribute('y', b.y - 2);
      r.setAttribute('width', b.width + 4); r.setAttribute('height', b.height + 4);
      g.prepend(r);
    });
  }, { once: true });

  // PLANNED, either the label under the Garden line or any planned stop: light them all.
  svg.querySelectorAll('.ring-planned, .st-planned').forEach((el) => {
    el.addEventListener('mouseenter', () => svg.classList.add('planned-lit'));
    el.addEventListener('mouseleave', () => svg.classList.remove('planned-lit'));
  });

  // Dwell: rest on a stop for DWELL ms and its label levels out and grows, on the assumption
  // you are trying to read it. CSS does the animating (render.py gives each label its angle and
  // pivot as custom properties from the start); this only flips a class.
  //
  // Once levelled the label has moved, so it is no longer under the pointer and hover would
  // swing it straight back. Only real pointer travel (HOLD px from where it levelled) puts it
  // back; until then what sits under the pointer is ignored.
  // DWELL is deliberately long: the idea is that you have just started wishing the label
  // would turn when it does, so it reads as mind-reading rather than as a hover effect.
  const DWELL = 1400, HOLD = 60;
  let dwellOn = null, timer = 0;
  const level = (el, on) => {
    el.classList.toggle('dwell-lit', on);  // the pointer has left the moved label; keep it lit anyway
    // Dim the rest of the map now, not on plain hover: a routed stop is already marked .on.
    svg.classList.toggle('dwelling', on && el.matches('a[data-route]'));
    el.querySelector('.lbl')?.classList.toggle('straight', on);
  };
  const undwell = () => {
    clearTimeout(timer);
    if (dwellOn) level(dwellOn, false);
    dwellOn = anchor = null;
  };
  // Returns true while a label is levelled and the pointer has not travelled away.
  const dwell = (el) => {
    if (anchor) {
      if (Math.hypot(at.x - anchor.x, at.y - anchor.y) < HOLD) return true;
      undwell();
    }
    if (el === dwellOn) return false;
    clearTimeout(timer);
    dwellOn = el;
    if (el) timer = setTimeout(() => {
      level(el, true);
      anchor = { x: at.x, y: at.y };  // where the pointer was when it levelled
    }, DWELL);
    return false;
  };

  // Edges: light the one nearest the pointer, and the two stops it joins. Picking by
  // distance rather than stacked hit areas keeps the dense overlapping bundles usable.
  const REACH = 10;  // screen pixels
  let edges = null, hot = null, frame = 0;
  const build = () => {  // deferred to first hover, so page load pays nothing
    const nodes = [];
    svg.querySelectorAll('a[data-k]').forEach((a) => {
      const c = a.querySelector('circle');
      if (c) nodes.push({ a, x: +c.getAttribute('cx'), y: +c.getAttribute('cy') });
    });
    const near = (x, y) => nodes.find((n) => Math.abs(n.x - x) < 1 && Math.abs(n.y - y) < 1);
    edges = [];
    svg.querySelectorAll('.links .link').forEach((p) => {
      const n = (p.getAttribute('d').match(/-?\d*\.?\d+/g) || []).map(Number);
      if (n.length < 4) return;
      // Edges are single quadratic curves (M x,y Q cx,cy x,y), so sample them with the formula:
      // getPointAtLength does the same job ~100x slower, a visible hitch on the first hover.
      // Anything else falls back to measuring the path.
      const quad = n.length === 6;
      const len = quad ? Math.hypot(n[2] - n[0], n[3] - n[1]) + Math.hypot(n[4] - n[2], n[5] - n[3]) : p.getTotalLength();
      const steps = Math.max(8, Math.ceil(len / 6)), pts = [];
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (let i = 0; i <= steps; i++) {
        const t = i / steps, u = 1 - t;
        const q = quad ? { x: u * u * n[0] + 2 * u * t * n[2] + t * t * n[4], y: u * u * n[1] + 2 * u * t * n[3] + t * t * n[5] }
                       : p.getPointAtLength(len * t);
        pts.push(q.x, q.y);
        x0 = Math.min(x0, q.x); x1 = Math.max(x1, q.x); y0 = Math.min(y0, q.y); y1 = Math.max(y1, q.y);
      }
      const ends = [near(n[0], n[1]), near(n[n.length - 2], n[n.length - 1])].filter(Boolean);
      edges.push({ p, pts, box: [x0, y0, x1, y1], ends });
    });
  };
  const gap2 = (px, py, pts) => {  // squared distance from a point to a sampled curve (no sqrt in the loop)
    let best = Infinity;
    for (let i = 0; i < pts.length - 2; i += 2) {
      const ax = pts[i], ay = pts[i + 1], dx = pts[i + 2] - ax, dy = pts[i + 3] - ay, len2 = dx * dx + dy * dy;
      const t = len2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
      const ex = ax + t * dx - px, ey = ay + t * dy - py, d = ex * ex + ey * ey;
      if (d < best) best = d;
    }
    return best;
  };
  const light = (e) => {
    if (e === hot) return;
    if (hot) { hot.p.classList.remove('lit'); hot.ends.forEach((n) => n.a.classList.remove('edge-lit')); }
    hot = e;
    if (hot) { hot.p.classList.add('lit'); hot.ends.forEach((n) => n.a.classList.add('edge-lit')); }
  };
  const pick = () => {
    frame = 0;
    const m = svg.getScreenCTM();
    if (!m || !at.on) return;
    const x = (at.x - m.e) / m.a, y = (at.y - m.f) / m.d;  // screen to map units (the map is only scaled and shifted)
    const reach = REACH / m.a;
    let best = null, bd2 = reach * reach;
    for (const e of edges) {
      const [x0, y0, x1, y1] = e.box;
      if (x < x0 - reach || x > x1 + reach || y < y0 - reach || y > y1 + reach) continue;  // cheap reject
      const d2 = gap2(x, y, e.pts);
      if (d2 < bd2) { bd2 = d2; best = e; }
    }
    light(best);
  };
  svg.addEventListener('pointermove', (e) => {
    if (e.pointerType === 'touch') return;
    at.x = e.clientX; at.y = e.clientY; at.on = true;
    const el = e.target.closest(STOP);
    if (dwell(el)) return;  // levelled and holding: leave the edge highlight as it is
    if (el) { light(null); return; }  // stops win
    if (!edges) build();
    if (!frame) frame = requestAnimationFrame(pick);
  });
  svg.addEventListener('pointerleave', () => { at.on = false; undwell(); light(null); });
})();

// Check for new pages: read every mapped page on the four sites, one hop out,
// and compare with what the map knows. Same rules as `build_map.py check`.
(() => {
  const box = document.querySelector('.scan'), data = document.getElementById('map-known');
  if (!box || !data || !window.DOMParser) return;
  let K;
  try { K = JSON.parse(data.textContent); } catch { return; }  // no data: no button, nothing else affected
  const btn = document.getElementById('scan-btn'), out = document.getElementById('scan-out');
  const known = new Set(K.known), goneOk = new Set(K.goneOk), hosts = new Set(K.hosts);
  const FILE = /\.(pdf|png|jpe?g|gif|svg|webp|zip|csv|json|txt|xml|ipynb)$/i;
  const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const norm = (href, base) => {  // mirrors norm() in tools/gcmap/crawl.py
    let u;
    try { u = new URL(href, base); } catch { return null; }
    if (!/^https?:$/.test(u.protocol)) return null;
    let host = u.host.toLowerCase();
    if (host === 'tahreemkarim.xyz') host = 'www.' + host;
    let path = u.pathname.replace(/(\/index)?\.html$/, '').replace(/\/+$/, '');
    if (host === 'github.com' || host === 'tahreemk13.github.io') path = path.toLowerCase();
    const url = 'https://' + host + path;
    return K.aliases[url] || url;
  };
  const read = async (url) => {
    try {
      const r = await fetch(url, { cache: 'no-store' });
      const html = r.ok && (r.headers.get('content-type') || '').includes('html') ? await r.text() : null;
      return { status: r.status, final: r.url || url, html };
    } catch { return { status: 0 }; }
  };
  const linksOf = (page) => {
    const doc = new DOMParser().parseFromString(page.html, 'text/html');
    return [...doc.querySelectorAll('a[href]')]
      .map((a) => a.getAttribute('href'))
      .filter((h) => !/^(#|mailto:|tel:|javascript:)/.test(h))
      .map((h) => norm(h, page.final)).filter(Boolean);
  };

  box.hidden = false;
  btn.addEventListener('click', async () => {
    btn.setAttribute('aria-busy', 'true');
    out.textContent = `Reading ${K.look.length} pages across four sites…`;
    const pages = await Promise.all(K.look.map(read));
    const reached = pages.filter((p) => p.status);
    if (!reached.length) {
      out.textContent = "Couldn't reach the sites just now. Try again in a minute.";
      btn.removeAttribute('aria-busy');
      return;
    }
    const gone = K.look.filter((u, i) => pages[i].status === 404 || pages[i].status === 410)
      .map((u) => norm(u)).filter((u) => !goneOk.has(u));
    const seen = new Set(pages.filter((p) => p.html).flatMap(linksOf));
    const cand = [...seen].filter((u) => hosts.has(new URL(u).host) && !known.has(u) && !FILE.test(u)).sort();
    const found = [];
    for (const [u, p] of await Promise.all(cand.map(async (u) => [u, await read(u)]))) {
      if (p.status === 200 && p.html) {
        const title = new DOMParser().parseFromString(p.html, 'text/html').title.split(/ [·|—–-] /)[0].trim();
        found.push({ u, title: title || new URL(u).pathname });
      }
    }

    let notified = false;
    if (found.length && K.notify) {
      const key = 'gc-notified:' + found.map((f) => f.u).join(' ');
      let told = false;
      try { told = !!localStorage.getItem(key); } catch {}
      if (!told) {
        try {
          const r = await fetch('https://ntfy.sh/' + encodeURIComponent(K.notify), {
            method: 'POST', headers: { Title: 'New page on your sites', Tags: 'station' },
            body: found.map((f) => `${f.title}: ${f.u}`).join('\n'),
          });
          notified = r.ok;
          if (notified) try { localStorage.setItem(key, '1'); } catch {}
        } catch {}
      } else notified = true;
    }

    const list = (items) => '<ul>' + items.join('') + '</ul>';
    let html = '';
    if (found.length) {
      html += `<strong>${found.length === 1 ? 'New page found!' : found.length + ' new pages found!'}</strong> `;
      html += notified ? 'Tahreem has been notified.' : "It's queued for the next map update.";
      html += list(found.map((f) => `<li><a href="${esc(f.u)}">${esc(f.title)}</a></li>`));
    }
    if (gone.length) {
      html += `<strong>${gone.length === 1 ? 'A page has gone missing.' : gone.length + ' pages have gone missing.'}</strong>`;
      html += list(gone.map((u) => `<li>${esc(K.names[u] || u)}</li>`));
    }
    out.innerHTML = html || `No new pages found. The map is up to date (${reached.length} pages checked).`;
    btn.textContent = 'Check again';
    btn.removeAttribute('aria-busy');
  });
})();
