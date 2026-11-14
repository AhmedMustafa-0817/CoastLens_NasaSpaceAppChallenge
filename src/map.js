// Full CoastLens map: every layer in public/data/layers.json, the decline zones and the NISAR alerts.
// Layers, legends and texts all come from the data files written by scripts/ (see scripts/README.md).
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { init, $ } from './core.js';
import { TILE_BASE } from './tiles.js';

init();
const get = (f) => fetch(import.meta.env.BASE_URL + 'data/' + f).then((r) => r.json());
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);

Promise.all([get('layers.json'), get('zones.geojson'), get('alerts.json')]).then(([cfg, zones, alerts]) => {
  const [w, s, e, n] = cfg.aoi.bbox, bounds = [[s, w], [n, e]];
  const map = L.map('map', { minZoom: cfg.minZoom, maxZoom: cfg.maxZoom, maxBounds: [[s - 0.3, w - 0.4], [n + 0.3, e + 0.4]] }).fitBounds(bounds);
  const bases = {
    img: L.tileLayer(cfg.basemaps[0].url, { attribution: cfg.basemaps[0].attribution, maxNativeZoom: 18 }),
    osm: L.tileLayer(cfg.basemaps[1].url, { attribution: cfg.basemaps[1].attribution, maxNativeZoom: 19 }),
  };
  let base = bases.img.addTo(map);
  $('#base').onchange = (ev) => { base.remove(); base = bases[ev.target.value].addTo(map); base.bringToBack(); };

  L.rectangle(bounds, { color: '#f4ede0', weight: 1.5, dashArray: '4 6', fill: false, interactive: false }).addTo(map);

  // decline zones (GMW v4.1): pink = loss
  L.geoJSON(zones, {
    style: { color: '#f0566f', weight: 2, dashArray: '6 4', fillColor: '#f0566f', fillOpacity: 0.08 },
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      lyr.bindTooltip(`<b>${esc(p.name)}</b><br>Mangrove ${p.peak_km2} km² (${p.peak_year}) → ${p.km2_2025} km² (2025): −${Math.round(p.lost_pct)}%`
        + (p.status ? `<br>NISAR 2025–26: ${esc(p.status)}` : ''), { sticky: true });
    },
  }).addTo(map);

  // NISAR alerts
  const row = (k, v) => `<dt>${k}</dt><dd>${esc(v)}</dd>`;
  alerts.alerts.forEach((a) => L.circleMarker([a.lat, a.lon], { radius: 8, color: '#f4ede0', weight: 2, fillColor: '#f0566f', fillOpacity: 1 })
    .bindPopup(`<div class="mapx-pop"><span class="mono">NISAR alert · ${esc(a.priority)} priority</span><h3>${esc(a.title)}</h3><dl>`
      + row('Observed', a.observed) + row('Evidence', a.evidence) + row('Confidence', a.confidence)
      + row('Possible causes (to verify)', a.possible_causes) + row('Next step', a.next_step)
      + `</dl><a href="${esc(a.maps_url)}" target="_blank" rel="noopener">Open in Google Maps ↗</a></div>`, { maxWidth: 340 })
    .addTo(map));

  // layer panel
  const on = new Map();
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
  let z = 10;
  document.querySelectorAll('.mapx-row').forEach((rowEl) => {
    const l = cfg.layers.find((x) => x.id === rowEl.dataset.id), box = rowEl.querySelector('input[type=checkbox]'), info = rowEl.querySelector('.mapx-info');
    box.onchange = () => {
      if (box.checked) {
        on.set(l.id, L.tileLayer(`${TILE_BASE}/${l.id}/{z}/{x}/{y}.png`, { bounds, minNativeZoom: 10, maxNativeZoom: l.maxNativeZoom ?? 14, zIndex: z++, attribution: 'Layers: CoastLens' }).addTo(map));
      } else {
        on.get(l.id)?.remove();
        on.delete(l.id);
      }
      info.hidden = !box.checked;
    };
    rowEl.querySelector('input[type=range]').oninput = (ev) => on.get(l.id)?.setOpacity(+ev.target.value);
  });
});
