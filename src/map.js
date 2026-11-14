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
    r.querySelector('input[type=checkbox]').onchange = (ev) => setLayer(id, ev.target.checked);
    r.querySelector('input[type=range]').oninput = (ev) => on.get(id)?.setOpacity(+ev.target.value);
  });

  // ---------- start-here stories ----------
  const zone = (id) => zones.features.find((f) => f.properties.id === id)?.properties;
  const zoneBounds = (...ids) => L.geoJSON({ type: 'FeatureCollection', features: zones.features.filter((f) => ids.includes(f.properties.id)) }).getBounds().pad(0.6);
  const gt = S.gmw_timeseries.summary, ai = S.nisar_pixel.ai, zA = zone('A');
  const alertBounds = L.latLngBounds(alerts.alerts.map((a) => [a.lat, a.lon])).pad(0.15);
  const rehri = L.latLngBounds([[24.775, 67.2], [24.825, 67.275]]);
  const STORIES = [
    { n: 1, title: 'Where are the mangroves?', layers: ['nisar_ai_mangrove_2025_26'], go: bounds,
      text: `${gt.last.km2.toFixed(0)} km² of mangrove grow along this coast (Global Mangrove Watch, ${gt.last.year}). Green is our map made from NISAR radar alone: ${ai.held_out_accuracy.overall_accuracy_pct}% accurate on areas it never trained on.`,
      key: 'Darker green = more certain it is mangrove.' },
    { n: 3, title: 'Places that keep dying', layers: ['gmw4_lossyear'], go: zoneBounds('A', 'B'),
      text: `Inside a growing coast, some patches lost forest year after year (pink dashed outlines). Zone ${zA.id} fell from ${zA.peak_km2.toFixed(2)} km² in ${zA.peak_year} to ${zA.km2_2025.toFixed(2)} km² in 2025: −${Math.round(zA.lost_pct)}%.`,
      key: 'Yellow = lost long ago, red = lost recently.' },
    { n: 5, title: 'Seeing through clouds', layers: [['nisar_hv_20261011', 1]], go: rehri,
      text: 'The photo underneath needs clear skies. NISAR sends its own radar signal, so it sees the forest day or night, in any weather. Drag the NISAR slider in the list below to fade between radar and photo.',
      key: 'Radar: bright = forest and buildings, black = water.' },
    { n: 2, title: '40 years of change', layers: ['gmw4_change_1985_2025'], go: bounds,
      text: `The mapped forest grew from ${gt.first.km2.toFixed(0)} km² in ${gt.first.year} to ${gt.last.km2.toFixed(0)} km² in ${gt.last.year} (+${Math.round(gt.net_change_pct)}%), much of it planted.`,
      key: 'Blue = new mangrove since 1985, red = mangrove lost since 1985.' },
    { n: 4, title: 'What is thinning right now', layers: ['nisar_hv_trend_2025_26'], go: alertBounds,
      text: `NISAR sees ${alerts.alerts.length} patches of mangrove thinning this year, each backed by at least ${Math.min(...alerts.alerts.map((a) => Object.values(a.signals ?? {}).filter(Boolean).length))} of 4 independent signals (pink dots). Click a dot for the evidence and directions. Next NISAR check: about ${alerts.next_nisar_pass}.`,
      key: 'Red = weakening compared with the rest of the forest, green = strengthening.' },
    { n: 6, title: 'Old satellite vs NISAR', layers: [['alos_hv_2024', 1], ['nisar_hv_20261011', 1]], go: zoneBounds('C'),
      text: 'Underneath: ALOS-2, the older L-band radar, which gives one picture a year. In zone C it showed the forest thinning in 2016, two years before ordinary photos did. On top: NISAR, every 12 days. Drag the NISAR slider to compare.',
      key: 'Both radars: bright = forest, black = water.' },
  ];
  const box = $('#stories');
  box.innerHTML = STORIES.map((st, i) => `<button class="mapx-story${i < 3 ? ' top' : ''}" data-i="${i}"><span class="mono">${String(st.n).padStart(2, '0')}</span>${esc(st.title)}</button>`).join('')
    + `<div class="mapx-story-text" id="storyText" hidden></div>`;
  const show = (i) => {
    const st = STORIES[i];
    [...on.keys()].forEach((id) => setLayer(id, false));
    st.layers.forEach((x) => (Array.isArray(x) ? setLayer(x[0], true, x[1]) : setLayer(x, true)));
    map.flyToBounds(st.go, { duration: 1.2 });
    box.querySelectorAll('.mapx-story').forEach((b) => b.setAttribute('aria-pressed', b.dataset.i == i));
    const t = $('#storyText');
    t.hidden = false;
    t.innerHTML = `<p>${esc(st.text)}</p><p class="mono mapx-meta">${esc(st.key)}</p><button class="mapx-reset mono">Reset map</button>`;
    t.querySelector('.mapx-reset').onclick = () => {
      [...on.keys()].forEach((id) => setLayer(id, false));
      box.querySelectorAll('.mapx-story').forEach((b) => b.setAttribute('aria-pressed', 'false'));
      t.hidden = true;
      map.flyToBounds(bounds, { duration: 1 });
    };
  };
  box.querySelectorAll('.mapx-story').forEach((b) => (b.onclick = () => show(+b.dataset.i)));
});
