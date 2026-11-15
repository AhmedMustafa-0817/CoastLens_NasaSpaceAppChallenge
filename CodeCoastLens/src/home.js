import { init, gsap, ScrollTrigger, SplitText, REDUCE, FINE, DPR, EASE, $, $$, clamp, lerp, fit, whileVisible } from './core.js';
import { mosaic, cover, drawClouds, BBOX } from './tiles.js';
import { Mangrove3D } from './mangrove3d.js';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { TILE_BASE } from './tiles.js';

init();
const OPTICAL = 's2_truecolor_2025_26', RADAR = 'nisar_hv_20261011';
const SAND_LIGHT = '#f4ede0', MOCHA = '#3a2c24', CORAL = '#f0566f';

/* ---------- 1 · hero: real image, illustrated cloud, radar lens ---------- */
{
  const c = $('#cHero'), g = c.getContext('2d'), hud = $('#hudPos');
  const base = mosaic(OPTICAL), rad = mosaic(RADAR, 12, '#141210');
  const lens = { x: 0, y: 0, tx: null, ty: null }, view = { zoom: REDUCE ? 1.04 : 1.4 };
  let t = 0;
  if (!REDUCE) gsap.to(view, { zoom: 1.04, duration: 5, ease: 'power3.out' }); // the descent
  c.addEventListener('pointermove', (e) => { const r = c.getBoundingClientRect(); lens.tx = (e.clientX - r.left) * DPR; lens.ty = (e.clientY - r.top) * DPR; });
  c.addEventListener('pointerleave', () => { lens.tx = null; });

  whileVisible(c, () => {
    if (fit(c)) { lens.x = c.width * 0.7; lens.y = c.height * 0.45; }
    const w = c.width, h = c.height;
    t += REDUCE ? 0 : 0.016;
    // with no pointer (touch, keyboard) the lens drifts slowly on its own
    const tx = lens.tx ?? w * (0.62 + 0.2 * Math.sin(t * 0.21)), ty = lens.ty ?? h * (0.46 + 0.16 * Math.sin(t * 0.33));
    lens.x = lerp(lens.x, tx, 0.07); lens.y = lerp(lens.y, ty, 0.07);
    g.imageSmoothingEnabled = true;
    cover(g, base, w, h, view.zoom);
    drawClouds(g, w, h, t);
    const r = Math.min(w, h) * (FINE ? 0.115 : 0.14), X = lens.x, Y = lens.y;
    // soft shadow so the lens sits above the cloud
    g.save();
    g.shadowColor = 'rgba(58, 44, 36, 0.4)'; g.shadowBlur = 26 * DPR; g.shadowOffsetY = 8 * DPR;
    g.fillStyle = '#141210'; g.beginPath(); g.arc(X, Y, r, 0, 7); g.fill();
    g.restore();
    g.save();
    g.beginPath(); g.arc(X, Y, r, 0, 7); g.clip();
    cover(g, rad, w, h, view.zoom);
    // a faint glass shade towards the rim
    const sh = g.createRadialGradient(X, Y, r * 0.55, X, Y, r);
    sh.addColorStop(0, 'rgba(20, 18, 16, 0)'); sh.addColorStop(1, 'rgba(20, 18, 16, 0.38)');
    g.fillStyle = sh; g.fillRect(X - r, Y - r, r * 2, r * 2);
    g.restore();
    // thin light rim, a hairline outer ring with four ticks, and one slow coral sweep
    g.lineCap = 'round';
    g.strokeStyle = SAND_LIGHT; g.lineWidth = 2 * DPR;
    g.beginPath(); g.arc(X, Y, r, 0, 7); g.stroke();
    const r1 = r + 9 * DPR;
    g.strokeStyle = 'rgba(58, 44, 36, 0.38)'; g.lineWidth = 1 * DPR;
    g.beginPath(); g.arc(X, Y, r1, 0, 7); g.stroke();
    for (let k = 0; k < 4; k++) {
      const a = (k / 4) * 6.283 - 0.785;
      g.beginPath(); g.moveTo(X + Math.cos(a) * (r1 - 4 * DPR), Y + Math.sin(a) * (r1 - 4 * DPR)); g.lineTo(X + Math.cos(a) * (r1 + 5 * DPR), Y + Math.sin(a) * (r1 + 5 * DPR)); g.stroke();
    }
    const sw = t * 0.5;
    g.strokeStyle = CORAL; g.lineWidth = 2.5 * DPR;
    g.beginPath(); g.arc(X, Y, r1, sw, sw + 0.7); g.stroke();
    g.fillStyle = CORAL; g.beginPath(); g.arc(X + Math.cos(sw + 0.7) * r1, Y + Math.sin(sw + 0.7) * r1, 3 * DPR, 0, 7); g.fill();
    g.lineCap = 'butt';
    // small label on a pill, so it reads over cloud and land alike
    const txt = 'RADAR VIEW';
    g.font = `500 ${9.5 * DPR}px "Geist Mono", monospace`; g.textAlign = 'center'; g.textBaseline = 'middle';
    const tw = g.measureText(txt).width + 30 * DPR, th = 20 * DPR, ly = Y - r1 - 20 * DPR;
    g.fillStyle = 'rgba(244, 237, 224, 0.86)';
    g.beginPath(); g.roundRect(X - tw / 2, ly - th / 2, tw, th, th / 2); g.fill();
    g.fillStyle = CORAL; g.beginPath(); g.arc(X - tw / 2 + 11 * DPR, ly, 2.5 * DPR, 0, 7); g.fill();
    g.fillStyle = MOCHA; g.fillText(txt, X + 5 * DPR, ly + 0.5 * DPR);
    g.textBaseline = 'alphabetic';
    // live coordinate of the lens centre (approximate, from the cover fit)
    const s = Math.max(w / base.width, h / base.height) * view.zoom;
    const u = (lens.x - (w - base.width * s) / 2) / (base.width * s), v = (lens.y - (h - base.height * s) / 2) / (base.height * s);
    const lon = lerp(BBOX[0], BBOX[2], clamp(u, 0, 1)), lat = lerp(BBOX[3], BBOX[1], clamp(v, 0, 1));
    hud.textContent = `${lat.toFixed(3)}°N ${lon.toFixed(3)}°E`;
  });
  if (!REDUCE) gsap.to('#hero .title', { yPercent: -30, opacity: 0, ease: 'none', scrollTrigger: { trigger: '#hero', start: 'top top', end: 'bottom 40%', scrub: 0.8 } });
}

/* ---------- 3 · the mangrove (Sketchfab model, dots pinned to real points on it) ---------- */
{
  const sec = $('#tree'), frameEl = $('#sfTree'), hots = $('#hots'), card = $('#acard'), seen = new Set();
  // Facts are for the red / stilt-root mangrove (Rhizophora) that the model shows.
  const parts = [
    { id: 'roots', label: 'Stilt roots', t: 'It breathes through its stilts.', a: 'Stilt roots', b: 'Your nose', p: 'The mud holds almost no oxygen. These arching roots prop the tree up, and tiny pores on them take in air whenever the tide is out.' },
    { id: 'leaf', label: 'Leaves', t: 'It drinks seawater and bins the salt.', a: 'Old leaves', b: 'Your kidneys', p: 'Its roots keep out most of the salt in seawater. The little that gets in is sent to older leaves, which turn yellow and drop off.' },
    { id: 'seed', label: 'Hanging pods', t: 'Its babies are born ready.', a: 'Hanging pods', b: 'A newborn', p: 'Each long green pod is a seedling already growing on the parent tree. When it drops, it floats on the tide until it lodges in mud.' },
    { id: 'fish', label: 'Under the water', t: 'It runs a daycare.', a: 'Root maze', b: 'A daycare', p: 'When the tide comes in, young fish and shrimp hide in this tangle of roots until they are big enough for open water.' },
  ];
  let tree = null;
  const wide = () => innerWidth > 900, copyEl = $('#tree .copy');
  // centre of the free area between the heading block and `until` (the card, or the section edge), as fractions of the viewer
  const freeSpot = (until) => {
    const f = frameEl.getBoundingClientRect(), c = copyEl.getBoundingClientRect();
    if (wide()) return { fx: clamp(((Math.max(f.left, c.right) + Math.min(f.right, until.left)) / 2 - f.left) / f.width, 0.15, 0.85), fy: 0.5 };
    return { fx: 0.5, fy: clamp(((Math.max(f.top, c.bottom) + Math.min(f.bottom, until.top)) / 2 - f.top) / f.height, 0.2, 0.8) };
  };
  const open = (a) => {
    seen.add(a.id); a.el.classList.add('seen');
    $('#foundN').textContent = seen.size;
    const next = parts.find((q) => !seen.has(q.id));
    card.hidden = false;
    card.innerHTML = `<span class="mono">${seen.size} of 4</span><h3>${a.t}</h3>
      <div class="eq"><div><b>${a.a}</b><span>the mangrove</span></div><span>=</span><div><b>${a.b}</b><span>you</span></div></div>
      <p>${a.p}</p>
      <div class="row">${next ? `<button class="btn" id="aNext">Next: ${next.label}</button>` : `<a class="btn" href="#fish">Why it matters</a>`}<button class="btn" id="aBack">Back to the tree</button></div>`;
    // glide to the part, centred in the space between the heading and the card (beside it on desktop, above it on phones)
    tree?.focus(a.id, freeSpot(card.getBoundingClientRect()));
    if (!REDUCE) gsap.from(card, { opacity: 0, y: 24, duration: 0.9, ease: EASE });
    if (next) $('#aNext').onclick = () => open(next);
    $('#aBack').onclick = () => { card.hidden = true; tree?.reset(); };
  };
  // "Visit the fish's home" in the next section scrolls back here and opens a card
  document.addEventListener('mangrove:open', (e) => {
    const a = parts.find((q) => q.id === e.detail);
    if (a) setTimeout(() => open(a), 1400); // once the scroll has (nearly) arrived
  });
  parts.forEach((a) => {
    a.el = document.createElement('button');
    a.el.className = 'hot';
    a.el.innerHTML = `<i></i><span>${a.label}</span>`;
    a.el.onclick = () => open(a);
    a.el.style.display = 'none';
    hots.appendChild(a.el);
  });

  // load the (heavy) model only when the section is about to be seen
  new IntersectionObserver(([e], io) => {
    if (!e.isIntersecting) return;
    io.disconnect();
    const edge = () => { const r = sec.getBoundingClientRect(); return { left: r.right, top: r.bottom }; };
    Mangrove3D(frameEl, $('#sfGrab'), { home: () => freeSpot(edge()) })
      .then((t) => {
        tree = t;
        sec.classList.add('ready');
        let rs = 0;
        addEventListener('resize', () => { clearTimeout(rs); rs = setTimeout(() => { if (!tree.st.focused) tree.reset(0); }, 200); });
        let busy = false;
        whileVisible(sec, () => {
          if (busy) return;
          busy = true;
          tree.frame().then((P) => {
            const f = frameEl.getBoundingClientRect(), s = sec.getBoundingClientRect();
            parts.forEach((a) => {
              const p = P[a.id], show = p.inView && (card.hidden || !seen.has(a.id));
              a.el.style.display = show ? 'flex' : 'none';
              a.el.classList.toggle('behind', !p.front);
              a.el.style.left = f.left - s.left + p.x + 'px';
              a.el.style.top = f.top - s.top + p.y + 'px';
            });
          }).finally(() => (busy = false));
        });
      })
      .catch(() => sec.classList.add('failed'));
  }, { rootMargin: '600px 0px' }).observe(sec);
}

/* ---------- 4 · why should I care: one fish travels from circle to circle as you scroll. No pin, no scroll lock ---------- */
{
  const tl = $('#fish .tl'), steps = $$('#fish .tl-step'), N = steps.length, hop = $('#fish .tl-hop');
  let target = 0, pos = 0, idx = -1;
  const light = (k) => {
    if (k === idx) return;
    idx = k;
    steps.forEach((el, i) => { el.classList.toggle('on', i <= k); el.classList.toggle('cur', i === k); });
  };
  // centre of each circle, measured against the timeline box
  const centres = () => {
    const base = tl.getBoundingClientRect();
    return steps.map((el) => {
      const r = el.querySelector('.ph').getBoundingClientRect();
      return { x: r.left - base.left + r.width / 2, y: r.top - base.top + r.height / 2 };
    });
  };
  let pts = [];
  const place = (f) => {
    const i = Math.min(N - 2, Math.floor(f)), t = f - i;
    const a = pts[i], b = pts[i + 1];
    hop.style.transform = `translate(${(a.x + (b.x - a.x) * t).toFixed(1)}px, ${(a.y + (b.y - a.y) * t).toFixed(1)}px) translate(-50%, -50%)`;
  };
  const measure = () => { pts = centres(); };
  if (REDUCE) {
    steps.forEach((el) => el.classList.add('on'));
    tl.style.setProperty('--p', 1);
    measure();
    hop.style.transform = '';
  } else {
    measure();
    window.addEventListener('resize', measure);
    ScrollTrigger.create({
      trigger: tl, start: 'top 72%', end: 'bottom 40%', scrub: true,
      onUpdate: (self) => { target = self.progress; tl.style.setProperty('--p', self.progress.toFixed(3)); },
    });
    gsap.ticker.add(() => {
      pos += (target * (N - 1) - pos) * 0.12;
      if (pts.length) place(Math.min(N - 1, pos));
      light(Math.min(N - 1, Math.round(pos)));
    });
  }
  $('#fish .home-link').addEventListener('click', (e) => document.dispatchEvent(new CustomEvent('mangrove:open', { detail: e.currentTarget.dataset.open })));
}

/* ---------- 5 · blind spot: frame expands, cloud rolls in, radar reveals ---------- */
{
  const c = $('#cBlind'), g = c.getContext('2d'), frame = $('#blind .frame'), intro = $('#blind .intro'), box = $('#blind .copy');
  const base = mosaic(OPTICAL), rad = mosaic(RADAR, 12, '#141210');
  const copy = [
    ['01 / 03 · Optical', 'A camera in space needs clear sky.', 'In the monsoon, cloud can hide this coast from ordinary satellite cameras. No picture, no answer.'],
    ['02 / 03 · NISAR pass', 'In 2025, a different kind of satellite.', 'NISAR, built by NASA and India’s ISRO, does not take photographs. It sends its own radar signal and listens for the echo.'],
    ['03 / 03 · Radar', 'It sees straight through.', 'Day or night, cloud or not, every 12 days. This is its real image of Karachi’s mangrove coast: bright is forest and town, dark is water.'],
  ];
  let p = REDUCE ? 1 : 0, stage = -1, t = 0;
  const sat = $('#blind .sat');

  const draw = () => {
    fit(c);
    const w = c.width, h = c.height;
    t += REDUCE ? 0 : 0.016;
    const grow = clamp(p / 0.14, 0, 1), cloud = clamp((p - 0.12) / 0.14, 0, 1), pass = clamp((p - 0.3) / 0.4, 0, 1), rev = clamp((p - 0.7) / 0.24, 0, 1);
    // the satellite slows down over the middle of the frame, so it stays in view while you scroll
    const u = 2 * pass - 1, glide = 0.5 + 0.5 * Math.sign(u) * Math.pow(Math.abs(u), 1.7);
    if (!REDUCE) {
      const k = 1 - gsap.parseEase('power2.inOut')(grow), m = innerWidth < 900;
      frame.style.clipPath = `inset(${(m ? 30 : 24) * k}% ${(m ? 12 : 30) * k}%)`;
    }
    if (!REDUCE) {
      const a = clamp((p - 0.09) / 0.07, 0, 1);
      intro.style.opacity = 1 - grow; intro.style.transform = `translateY(${-40 * grow}px)`;
      box.style.opacity = a; box.style.transform = `translateY(${30 * (1 - a)}px)`;
    }
    g.imageSmoothingEnabled = true;
    cover(g, base, w, h, 1.25 - 0.2 * grow);
    drawClouds(g, w, h, t, cloud * (1 - rev * 0.35));
    if (rev > 0) {
      g.save(); g.beginPath(); g.rect(0, 0, w * rev, h); g.clip();
      cover(g, rad, w, h, 1.05);
      g.restore();
      if (rev < 1) { const gr = g.createLinearGradient(w * rev - 90 * DPR, 0, w * rev, 0); gr.addColorStop(0, 'rgba(176,120,42,0)'); gr.addColorStop(1, 'rgba(176,120,42,.85)'); g.fillStyle = gr; g.fillRect(w * rev - 90 * DPR, 0, 90 * DPR, h); }
    }
    if (pass > 0 && pass < 1) { // the satellite crossing, with its radar beam
      const X = lerp(-80 * DPR, w + 80 * DPR, glide), Y = h * 0.2;
      g.fillStyle = 'rgba(176,120,42,.16)'; g.beginPath(); g.moveTo(X - 8 * DPR, Y); g.lineTo(X - 190 * DPR, h); g.lineTo(X + 190 * DPR, h); g.lineTo(X + 8 * DPR, Y); g.fill();
    }
    // the 3D satellite follows the same path as the beam, as a DOM element on top of the canvas
    const fade = clamp(Math.min(pass * 8, (1 - pass) * 8), 0, 1);
    if (pass > 0 && pass < 1) {
      const X = lerp(-80 * DPR, w + 80 * DPR, glide), Y = h * 0.2;
      sat.style.transform = `translate(${(X / w * c.clientWidth).toFixed(1)}px, ${(Y / h * c.clientHeight).toFixed(1)}px) translate(-50%, -50%)`;
      sat.style.opacity = fade.toFixed(2);
    } else {
      sat.style.opacity = '0';
    }
    const s = p < 0.3 ? 0 : p < 0.7 ? 1 : 2;
    if (s !== stage) { stage = s; $('#bStage').textContent = copy[s][0]; $('#bH').textContent = copy[s][1]; $('#bD').textContent = copy[s][2]; }
  };
  whileVisible($('#blind'), draw);
  if (!REDUCE) {
    ScrollTrigger.create({ trigger: '#blind', start: 'top top', end: '+=420%', pin: true, scrub: 1, onUpdate: (s) => (p = s.progress) });
  }
}

/* ---------- 6 · three scales, three small charts ---------- */
function lineChart(sel, pts, labels, col) {
  const lo = Math.min(...pts), hi = Math.max(...pts), X = (i) => 6 + (i * 288) / (pts.length - 1), Y = (v) => 92 - ((v - lo) / (hi - lo)) * 74;
  const d = pts.map((v, i) => `${X(i)},${Y(v)}`).join(' ');
  $(sel).innerHTML = `<line x1="6" x2="294" y1="100" y2="100" stroke="currentColor" opacity=".25"/>
    <polyline points="${d}" fill="none" stroke="${col}" stroke-width="2.5" pathLength="1" stroke-dasharray="1" class="draw"/>
    ${pts.map((v, i) => `<circle cx="${X(i)}" cy="${Y(v)}" r="4" fill="${col}"/>`).join('')}
    <text x="6" y="116" font-size="10" font-family="Geist Mono" fill="currentColor" opacity=".7">${labels[0]}</text>
    <text x="294" y="116" font-size="10" text-anchor="end" font-family="Geist Mono" fill="currentColor" opacity=".7">${labels[1]}</text>`;
}
lineChart('#gWorld', [152604, 147359], ['1996 · 152,604 km²', '2020 · 147,359 km²'], MOCHA);
lineChart('#gDelta', [50973, 101446], ['1990 · 50,973 ha', '2023 · 101,446 ha'], MOCHA);
if (!REDUCE) $$('.draw').forEach((l) => gsap.from(l, { strokeDashoffset: 1, duration: 2, ease: 'power2.inOut', scrollTrigger: { trigger: l, start: 'top 85%', once: true } }));

/* ---------- 6 · the proof: one fixed map of the forest that was lost ----------
   Global Mangrove Watch v4.1 loss year (yellow long ago, red recently) and the decline zones, over our own
   Sentinel-2 photo. Framed on the four zones east of Rehri Goth (A, B, C, G). No controls: it is evidence, not a tool;
   the full map is one click away. Loaded only when the section comes near, so its tiles do not slow the page. */
{
  const el = $('#impactMap');
  if (el) new IntersectionObserver(([e], io) => {
    if (!e.isIntersecting) return;
    io.disconnect();
    const [w, s, ee, n] = BBOX, box = [[s, w], [n, ee]];
    const view = L.latLngBounds([[24.738, 67.276], [24.794, 67.344]]);
    const map = L.map(el, {
      zoomControl: false, dragging: false, scrollWheelZoom: false, doubleClickZoom: false, boxZoom: false,
      keyboard: false, touchZoom: false, tap: false, attributionControl: true, zoomSnap: 0.25,
    }).fitBounds(view);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { attribution: 'Basemap: Esri, Maxar, Earthstar Geographics (reference only)', maxNativeZoom: 18, opacity: 0.45 }).addTo(map);
    L.tileLayer(`${TILE_BASE}/s2_truecolor_2025_26/{z}/{x}/{y}.png`, { bounds: box, minNativeZoom: 10, maxNativeZoom: 15, attribution: 'Photo: Sentinel-2 2025–26 (Copernicus)' }).addTo(map);
    L.tileLayer(`${TILE_BASE}/gmw4_lossyear/{z}/{x}/{y}.png`, { bounds: box, minNativeZoom: 10, maxNativeZoom: 14, attribution: 'Global Mangrove Watch v4.1, CoastLens' }).addTo(map);
    fetch(import.meta.env.BASE_URL + 'data/zones.geojson').then((r) => r.json()).then((zones) => {
      L.geoJSON(zones, {
        style: { color: '#f0566f', weight: 2.5, dashArray: '6 4', fillColor: '#f0566f', fillOpacity: 0.06 },
        onEachFeature: (f, lyr) => {
          const p = f.properties;
          // the worst zone carries its number on the map; the rest say theirs on hover
          lyr.bindTooltip(`Zone ${p.id}: ${p.peak_km2.toFixed(2)} → ${p.km2_2025.toFixed(2)} km² (−${Math.round(p.lost_pct)}%)`,
            { permanent: p.id === 'A', className: 'impact-tip',
              ...(innerWidth < 700 ? { direction: 'top', offset: [0, -6] } : { direction: 'right', offset: [8, 0] }) });
        },
      }).addTo(map);
      const a = zones.features.find((f) => f.properties.id === 'A')?.properties;
      if (a) $('#impactLine').textContent = `Across the whole coast the mapped forest grew. But in ${zones.features.length} small zones it kept shrinking: in the worst one, ${a.peak_km2.toFixed(2)} km² of mangrove in ${a.peak_year} became ${a.km2_2025.toFixed(2)} km² by 2025 (−${Math.round(a.lost_pct)}%).`;
    });
    addEventListener('resize', () => { map.invalidateSize(); map.fitBounds(view); });
  }, { rootMargin: '400px 0px' }).observe(el);
}
