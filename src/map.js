// Full CoastLens map: every layer in public/data/layers.json, the decline zones and the NISAR alerts,
// plus six "start here" stories for non-specialists. Texts and numbers come from the data files
// written by scripts/ (see scripts/README.md).
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { init, $ } from './core.js';
import { TILE_BASE } from './tiles.js';

init();
const get = (f) => fetch(import.meta.env.BASE_URL + 'data/' + f).then((r) => r.json());
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const BACKGROUND = 's2_truecolor_2025_26'; // our own cloud-free Sentinel-2 photo, one season, no seams

Promise.all([get('layers.json'), get('zones.geojson'), get('alerts.json'), get('stats.json')]).then(([cfg, zones, alerts, S]) => {
  const [w, s, e, n] = cfg.aoi.bbox, bounds = [[s, w], [n, e]];
  const map = L.map('map', { minZoom: cfg.minZoom, maxZoom: cfg.maxZoom, maxBounds: [[s - 0.3, w - 0.4], [n + 0.3, e + 0.4]] }).fitBounds(bounds);

  // ---------- background ----------
  const esri = L.tileLayer(cfg.basemaps[0].url, { attribution: cfg.basemaps[0].attribution, maxNativeZoom: 18 });
  const osm = L.tileLayer(cfg.basemaps[1].url, { attribution: cfg.basemaps[1].attribution, maxNativeZoom: 19 });
  const ours = L.tileLayer(`${TILE_BASE}/${BACKGROUND}/{z}/{x}/{y}.png`, { bounds, minNativeZoom: 10, maxNativeZoom: 15, zIndex: 2, attribution: 'Photo: Sentinel-2 2025–26 (Copernicus), CoastLens' });
  const setBase = (v) => {
    [esri, osm, ours].forEach((l) => l.remove());
    if (v === 'ours') { esri.setOpacity(0.45).addTo(map); ours.addTo(map); }
    else if (v === 'img') esri.setOpacity(1).addTo(map);
    else osm.addTo(map);
  };
  setBase('ours');
  $('#base').onchange = (ev) => setBase(ev.target.value);

  L.rectangle(bounds, { color: '#f4ede0', weight: 1.5, dashArray: '4 6', fill: false, interactive: false }).addTo(map);

  // ---------- decline zones (GMW v4.1): pink = loss ----------
  L.geoJSON(zones, {
    style: { color: '#f0566f', weight: 2, dashArray: '6 4', fillColor: '#f0566f', fillOpacity: 0.08 },
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      lyr.bindTooltip(`<b>${esc(p.name)}</b><br>Mangrove ${p.peak_km2} km² (${p.peak_year}) → ${p.km2_2025} km² (2025): −${Math.round(p.lost_pct)}%`
        + (p.status ? `<br>NISAR 2025–26: ${esc(p.status)}` : ''), { sticky: true });
    },
  }).addTo(map);

  // ---------- NISAR alerts ----------
  const row = (k, v) => `<dt>${k}</dt><dd>${esc(v)}</dd>`;
  alerts.alerts.forEach((a) => L.circleMarker([a.lat, a.lon], { radius: 8, color: '#f4ede0', weight: 2, fillColor: '#f0566f', fillOpacity: 1 })
    .bindPopup(`<div class="mapx-pop"><span class="mono">NISAR alert · ${esc(a.priority)} priority</span><h3>${esc(a.title)}</h3><dl>`
      + row('Observed', a.observed) + row('Evidence', a.evidence) + row('Confidence', a.confidence)
      + row('Possible causes (to verify)', a.possible_causes) + row('Next step', a.next_step)
      + `</dl><a href="${esc(a.maps_url)}" target="_blank" rel="noopener">Open in Google Maps ↗</a></div>`, { maxWidth: 340 })
    .addTo(map));

  // ---------- layer panel ----------
  const on = new Map();
  let z = 10;
  const legend = (lg) => {
    if (!lg) return '';
    if (lg.type === 'gradient') return `<div class="mapx-bar" style="background:linear-gradient(90deg,${lg.colors.join(',')})"></div><div class="mapx-ends mono"><span>${esc(lg.min)}</span><span>${esc(lg.max)}</span></div>`;
    if (!lg.items) return lg.note ? `<p class="mono mapx-meta">${esc(lg.note)}</p>` : '';
    return `<ul class="mapx-classes">${lg.items.map((i) => `<li><i style="background:${i.color}"></i>${esc(i.label)}</li>`).join('')}</ul>`;
  };
  $('#groups').innerHTML = cfg.groups.map((g) => {
    const ls = cfg.layers.filter((l) => l.group === g.id && l.status === 'ready');
    if (!ls.length) return '';
    return `<section class="mapx-group"><h2 class="mono">${esc(g.title)}</h2>${ls.map((l) => `
      <div class="mapx-row" data-id="${l.id}">
        <label><input type="checkbox"><span>${esc(l.title)}</span></label>
        <div class="mapx-info" hidden>
          <input type="range" min="0" max="1" step="0.05" value="1" aria-label="${esc(l.title)} opacity">
          ${legend(l.legend)}
          <p>${esc(l.explain)}</p>
          ${l.caveat ? `<p class="mapx-caveat">${esc(l.caveat)}</p>` : ''}
          <p class="mono mapx-meta">${esc(l.sensor)} · ${esc(l.dates)} · ${esc(l.resolution)}</p>
        </div>
      </div>`).join('')}</section>`;
  }).join('');
  const rows = new Map([...document.querySelectorAll('.mapx-row')].map((r) => [r.dataset.id, r]));
  const setLayer = (id, show, opacity = 1) => {
    const l = cfg.layers.find((x) => x.id === id), r = rows.get(id);
    if (!l || !r) return;
    on.get(id)?.remove();
    on.delete(id);
    if (show) on.set(id, L.tileLayer(`${TILE_BASE}/${id}/{z}/{x}/{y}.png`, { bounds, minNativeZoom: 10, maxNativeZoom: l.maxNativeZoom ?? 14, zIndex: z++, opacity, attribution: 'Layers: CoastLens' }).addTo(map));
    r.querySelector('input[type=checkbox]').checked = show;
    r.querySelector('input[type=range]').value = opacity;
    r.querySelector('.mapx-info').hidden = !show;
  };
  rows.forEach((r, id) => {
    r.querySelector('input[type=checkbox]').onchange = (ev) => { setLayer(id, ev.target.checked); story = null; markStory(); renderLegend(); };
    r.querySelector('input[type=range]').oninput = (ev) => on.get(id)?.setOpacity(+ev.target.value);
  });

  // ---------- start-here stories (plain language for first-time visitors) ----------
  const zone = (id) => zones.features.find((f) => f.properties.id === id)?.properties;
  const zoneBounds = (...ids) => L.geoJSON({ type: 'FeatureCollection', features: zones.features.filter((f) => ids.includes(f.properties.id)) }).getBounds().pad(0.6);
  const gt = S.gmw_timeseries.summary, zA = zone('A');
  const alertBounds = L.latLngBounds(alerts.alerts.map((a) => [a.lat, a.lon])).pad(0.15);
  const rehri = L.latLngBounds([[24.775, 67.2], [24.825, 67.275]]);
  const sq = (color, label) => ({ sq: color, label });
  const bar = (from, to, a, b) => ({ bar: [from, to], a, b });
  const STORIES = [
    { title: 'Where are the mangroves?', layers: ['nisar_ai_mangrove_2025_26'], go: bounds,
      text: `Mangroves are trees that grow in seawater. They are nurseries for young fish, shrimp and crabs, and they shield the shore from waves and storms. Karachi's coast has about ${gt.last.km2.toFixed(0)} km² of them. The green on the map is where NISAR, a radar satellite, finds them.`,
      key: [bar('#ffffd2', '#0a8c3c', 'Maybe forest', 'Mangrove forest')] },
    { title: 'Places that keep dying', layers: ['gmw4_lossyear'], go: zoneBounds('A', 'B'),
      text: `Most of this coast is greener than it was 40 years ago. But in a few places the forest keeps disappearing, year after year. In the worst one, about four-fifths of the forest is gone since ${zA.peak_year} (${zA.peak_km2.toFixed(2)} km² down to ${zA.km2_2025.toFixed(2)} km²). Once mangroves go, the shore behind them loses its shield.`,
      key: [sq('#ffe678', 'Forest lost long ago'), sq('#e04a3a', 'Forest lost a few years ago'), sq('#c80028', 'Forest lost recently')] },
    { title: 'Seeing through clouds', layers: [['nisar_hv_20261011', 1]], go: rehri,
      text: 'Ordinary satellites take photos, so clouds and night hide the forest, often in the monsoon, exactly when storms hit. NISAR uses radar instead: it sees through cloud, day or night. Use the slider on the map to compare the photo with what NISAR sees.',
      key: [sq('#d9d9d9', 'Trees and buildings (strong echo)'), sq('#111111', 'Water (no echo)')], fade: ['nisar_hv_20261011', 'Photo', 'Radar'] },
    { title: '40 years of change', layers: ['gmw4_change_1985_2025'], go: bounds,
      text: `In ${gt.first.year} there were about ${gt.first.km2.toFixed(0)} km² of mangroves here. In ${gt.last.year} there were about ${gt.last.km2.toFixed(0)} km², much of it planted by people. Good news, but a big total can hide the places that are still being lost.`,
      key: [sq('#1d6fe0', 'New forest since 1985'), sq('#e63946', 'Forest lost since 1985')] },
    { title: 'What is thinning right now', layers: ['nisar_hv_trend_2025_26'], go: alertBounds,
      text: `NISAR checks this coast every 12 days. The ${alerts.alerts.length} pink dots are patches where the forest is getting thinner right now, backed up by other satellites too. That is where conservation teams should look first. Click a dot to see why, and how to get there.`,
      key: [sq('#c82828', 'Forest getting weaker'), sq('#f5f5f0', 'No change'), sq('#1e9646', 'Forest getting stronger')] },
    { title: 'Old satellite vs NISAR', layers: [['alos_hv_2024', 1], ['nisar_hv_20261011', 1]], go: zoneBounds('C'),
      text: 'Before NISAR, radar gave us just one picture a year. In this spot it showed the forest thinning in 2016, two years before ordinary photos noticed. NISAR now checks every 12 days, so trouble can be caught while there is still time to act. Use the slider on the map to compare old and new.',
      key: [sq('#d9d9d9', 'Forest (strong echo)'), sq('#111111', 'Water (no echo)')], fade: ['nisar_hv_20261011', 'Old (2024)', 'NISAR (2026)'] },
  ];
  let story = null;
  const box = $('#stories');
  box.innerHTML = STORIES.map((st, i) => `<button class="mapx-story${i < 3 ? ' top' : ''}" data-i="${i}"><span class="mono">${String(i + 1).padStart(2, '0')}</span>${esc(st.title)}</button>`).join('')
    + `<div class="mapx-story-text" id="storyText" hidden></div>`;
  const markStory = () => box.querySelectorAll('.mapx-story').forEach((b) => b.setAttribute('aria-pressed', String(story != null && +b.dataset.i === story)));

  // ---------- floating legend (bottom-right of the map) ----------
  const lg = $('#legend');
  L.DomEvent.disableClickPropagation(lg);
  L.DomEvent.disableScrollPropagation(lg);
  const item = (k) => (k.bar
    ? `<div class="mapx-lg-bar" style="background:linear-gradient(90deg,${k.bar[0]},${k.bar[1]})"></div><div class="mapx-lg-ends"><span>${esc(k.a)}</span><span>${esc(k.b)}</span></div>`
    : `<li><i style="background:${k.sq}"></i>${esc(k.label)}</li>`);
  const always = '<ul class="mapx-lg-list"><li><i class="mapx-sym-zone"></i>Area that keeps losing forest</li><li><i class="mapx-sym-alert"></i>Thinning now: check here first</li></ul>';
  function renderLegend() {
    let body = '';
    if (story != null) {
      const st = STORIES[story];
      const bars = st.key.filter((k) => k.bar).map(item).join(''), sqs = st.key.filter((k) => !k.bar).map(item).join('');
      body = (st.fade ? `<label class="mapx-fade"><span>${esc(st.fade[1])}</span><input type="range" min="0" max="1" step="0.05" value="${on.get(st.fade[0])?.options.opacity ?? 1}" aria-label="Slide between ${esc(st.fade[1])} and ${esc(st.fade[2])}"><span>${esc(st.fade[2])}</span></label>` : '')
        + bars + (sqs ? `<ul class="mapx-lg-list">${sqs}</ul>` : '');
    } else {
      body = [...on.keys()].map((id) => cfg.layers.find((l) => l.id === id)).filter(Boolean)
        .map((l) => `<div class="mapx-lg-layer"><b>${esc(l.title)}</b>${legend(l.legend)}</div>`).join('');
    }
    lg.innerHTML = `<h3>What the colours mean</h3>${body}${always}`;
    const f = lg.querySelector('.mapx-fade input');
    if (f) {
      const id = STORIES[story].fade[0], rowRange = rows.get(id).querySelector('input[type=range]');
      f.oninput = (ev) => { on.get(id)?.setOpacity(+ev.target.value); rowRange.value = ev.target.value; };
    }
  }
  renderLegend();

  const show = (i) => {
    const st = STORIES[i];
    [...on.keys()].forEach((id) => setLayer(id, false));
    st.layers.forEach((x) => (Array.isArray(x) ? setLayer(x[0], true, x[1]) : setLayer(x, true)));
    story = i;
    markStory();
    renderLegend();
    map.flyToBounds(st.go, { duration: 1.2 });
    const t = $('#storyText');
    t.hidden = false;
    t.innerHTML = `<p>${esc(st.text)}</p><button class="mapx-reset mono">Reset map</button>`;
    const panel = $('.mapx-panel');
    panel.scrollTo({ top: Math.max(0, t.offsetTop - panel.offsetTop - 120), behavior: 'smooth' });
    t.querySelector('.mapx-reset').onclick = () => {
      [...on.keys()].forEach((id) => setLayer(id, false));
      story = null;
      markStory();
      renderLegend();
      t.hidden = true;
      map.flyToBounds(bounds, { duration: 1 });
    };
  };
  box.querySelectorAll('.mapx-story').forEach((b) => (b.onclick = () => show(+b.dataset.i)));
});
