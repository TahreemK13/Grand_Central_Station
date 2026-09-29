// Grand Central hub: the menu, the system map (centering, reveal, route tracing)
// and the live check under it. Loaded at the end of index.html.

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

// System map: opens centered on Grand Central, reveals once, traces routes.
(() => {
  const svg = document.querySelector('svg.net');
  if (!svg) return;
  const sc = svg.parentElement, note = document.getElementById('trace-note'), rest = note.textContent;

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
    note.textContent = rest;
  };
  const show = (a) => {
    clear();
    const route = a.dataset.route.split(' ');
    line.setAttribute('points', route.map((k) => pos[k]).join(' '));
    svg.insertBefore(line, svg.querySelector('[data-k]'));
    lit = route.map((k) => stop[k]);
    lit.forEach((el) => el.classList.add('on'));
    svg.classList.add('tracing');
    note.textContent = a.querySelector('title').textContent;
  };
  const on = (e) => { const a = e.target.closest('[data-route]'); if (a) show(a); else clear(); };
  svg.addEventListener('pointerover', on);
  svg.addEventListener('focusin', on);
  svg.addEventListener('pointerleave', clear);
  svg.addEventListener('focusout', clear);
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
