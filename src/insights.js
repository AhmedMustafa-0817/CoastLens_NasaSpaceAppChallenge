import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { init, gsap, REDUCE, EASE, $, $$, clamp, finding, loadStats } from './core.js';
import { TILE_BASE, BBOX } from './tiles.js';

init();
const GREEN = '#9fb07f', LAND = '#cdbfa3', WATERC = '#8fa39c';
const f1 = (n) => n.toFixed(1), minus = (s) => String(s).replace('-', '−');

/** Multi-line time chart. series: [{color, pts:[[xValue, y|null]]}] */
function lines(sel, series, { y0, y1, ticks, xLabels, unit = '', label }) {
  const W = 900, H = 300, l = 56, r = 20, t = 16, b = 40;
  const xs = series[0].pts.map((p) => p[0]), x0 = Math.min(...xs), x1 = Math.max(...xs);
  const X = (v) => l + ((v - x0) / (x1 - x0)) * (W - l - r), Y = (v) => t + (1 - (v - y0) / (y1 - y0)) * (H - t - b);
  const path = (pts) => { let d = '', pen = false; for (const [x, y] of pts) { if (y == null) { pen = false; continue; } d += `${pen ? 'L' : 'M'}${X(x).toFixed(1)},${Y(y).toFixed(1)}`; pen = true; } return d; };
  const el = $(sel);
  el.setAttribute('aria-label', label);
  el.innerHTML = ticks.map((v) => `<line class="ax" x1="${l}" x2="${W - r}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${l - 10}" y="${Y(v) + 4}" text-anchor="end">${minus(v)}${unit}</text>`).join('')
    + xLabels.map(([v, s]) => `<text x="${X(v)}" y="${H - 12}" text-anchor="middle">${s}</text>`).join('')
    + series.map((s) => `<path d="${path(s.pts)}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" class="ln"/>` + s.pts.filter((p) => p[1] != null).map(([x, y]) => `<circle cx="${X(x)}" cy="${Y(y)}" r="2.6" fill="${s.color}"><title>${y}</title></circle>`).join('')).join('');
  if (REDUCE) return;
  $$('.ln', el).forEach((p) => { const n = p.getTotalLength(); gsap.fromTo(p, { strokeDasharray: n, strokeDashoffset: n }, { strokeDashoffset: 0, duration: 2.6, ease: 'power2.inOut', scrollTrigger: { trigger: el, start: 'top 82%', once: true } }); });
}
const day = (d) => Date.parse(d) / 864e5;
const months = (a, b) => { const out = []; const d = new Date(a); d.setUTCDate(1); d.setUTCMonth(d.getUTCMonth() + 1); while (d <= new Date(b)) { out.push([d / 864e5, d.toLocaleString('en', { month: 'short', timeZone: 'UTC' }) + (d.getUTCMonth() === 0 ? ' ’' + String(d.getUTCFullYear()).slice(2) : '')]); d.setUTCMonth(d.getUTCMonth() + 1); } return out; };

loadStats().then(async (S) => {
  const gt = S.gmw_timeseries, ar = gt.years.filter((y) => y.year % 10 === 5), a0 = ar[0].km2, a1 = ar.at(-1).km2;
  const zones = S.decline_zones.zones, z0 = zones[0], lostPct = zones.map((z) => z.lost_pct);
  const v3 = S.mangrove_area.years[0], v4same = gt.years.find((y) => y.year === v3.year).km2;
  $('#stats4').innerHTML = [
    [f1(a1), `km² mapped as mangrove in ${ar.at(-1).year}`],
    [f1(a0), `km² in ${ar[0].year}`],
    [`<em class="pink">${zones.length}</em>`, `zones that kept losing forest (−${Math.round(Math.min(...lostPct))}% to −${Math.round(Math.max(...lostPct))}%)`],
    [`${ar[0].year}–${String(ar.at(-1).year).slice(2)}`, 'Global Mangrove Watch v4.1, yearly maps'],
  ].map(([b, s], i) => `<div data-reveal="${i * 0.1}"><b class="num">${b}</b><span>${s}</span></div>`).join('');
  if (!REDUCE) gsap.to('#stats4 > div', { opacity: 1, y: 0, duration: 1.4, ease: EASE, stagger: 0.12, delay: 0.6 });

  // 01 area bars
  {
    const W = 900, H = 300, base = 250, bw = 120, el = $('#chArea');
    el.setAttribute('aria-label', 'Mapped mangrove area: ' + ar.map((y) => `${y.year}: ${y.km2} km²`).join(', '));
    el.innerHTML = `<line class="ax" x1="0" x2="${W}" y1="${base}" y2="${base}"/>` + ar.map((y, i) => {
      const x = 40 + i * ((W - 80 - bw) / (ar.length - 1)), h = (y.km2 / 200) * 220;
      return `<rect class="bar" x="${x}" y="${base - h}" width="${bw}" height="${h}" fill="#4a5d3a"/>
        <text x="${x + bw / 2}" y="${base - h - 12}" text-anchor="middle" style="font:400 30px 'Instrument Serif',serif;letter-spacing:0">${y.km2.toFixed(1)}</text>
        <text x="${x + bw / 2}" y="${base + 24}" text-anchor="middle">${y.year}</text>`;
    }).join('');
    if (!REDUCE) gsap.from('#chArea .bar', { scaleY: 0, transformOrigin: '50% 100%', duration: 1.8, ease: EASE, stagger: 0.16, scrollTrigger: { trigger: el, start: 'top 82%', once: true } });
  }
  $('#f1').innerHTML = finding({
    measured: `Mangrove was mapped on ${f1(a0)} km² in ${ar[0].year} and ${f1(a1)} km² in ${ar.at(-1).year} (+${Math.round(gt.summary.net_change_pct)}%), flattening since about 2015. But in ${zones.length} small zones the forest kept shrinking year after year; in the largest (zone ${z0.id}, ${z0.centroid[1].toFixed(3)}°N ${z0.centroid[0].toFixed(3)}°E) it fell from ${z0.peak_km2.toFixed(2)} km² in ${z0.peak_year} to ${z0.km2_2025.toFixed(2)} km² in 2025. Source: Global Mangrove Watch v4.1, about 25 m, area computed by CoastLens.`,
    maybe: 'The growth fits restoration planting and mangrove spreading onto new mudflats. The shrinking zones could be clearing, land filling, cutting, grazing or erosion; some losses there were sudden, which points to clearing or filling rather than slow die-back.',
    confidence: 'Medium', why: `One external map product, not field-checked. The older GMW v3 maps disagree strongly: they put ${f1(v3.km2)} km² here in ${v3.year}, where v4.1 puts ${f1(v4same)} km².`,
  });

  // 02 NDVI
  const nd = S.ndvi_in_mangroves.series, s1 = S.s1_vh_in_mangroves.series;
  lines('#chNdvi', [{ color: '#4a5d3a', pts: nd.map((d, i) => [i, d.mean]) }], { y0: 0.44, y1: 0.58, ticks: [0.44, 0.48, 0.52, 0.56], xLabels: nd.map((d, i) => [i, d.season]), label: 'Mean NDVI inside mangroves: ' + nd.map((d) => `${d.season}: ${d.mean}`).join(', ') });
  $('#f2').innerHTML = finding({
    measured: `Mean NDVI inside the 2020 mangrove area rose from ${nd[0].mean.toFixed(3)} (${nd[0].season}) to ${nd.at(-1).mean.toFixed(3)} (${nd.at(-1).season}), Landsat 8, 30 m. Sentinel-1 radar over the same area was flat: ${minus(s1[0].mean_db)} dB (${s1[0].season}) and ${minus(s1[1].mean_db)} dB (${s1[1].season}).`,
    maybe: 'A denser canopy, young planted or regrown trees maturing, or wetter recent years. Tide height at the time of each image also shifts greenness.',
    confidence: 'Medium', why: 'Two independent sensors show no decline. Greenness is not the same thing as mangrove area.',
  });

  // 03 NISAR series
  const bs = S.nisar_timeseries.backscatter.series, co = S.nisar_timeseries.coherence.series, ok = bs.filter((d) => d.mangrove_hv != null);
  const xl = months(bs[0].date, bs.at(-1).date);
  lines('#chHv', [['mangrove_hv', GREEN], ['land_hv', LAND], ['water_hv', WATERC]].map(([k, color]) => ({ color, pts: bs.map((d) => [day(d.date), d[k]]) })), { y0: -28, y1: -12, ticks: [-28, -24, -20, -16, -12], unit: ' dB', xLabels: xl, label: `NISAR HV echo by surface, ${bs.length} passes from ${bs[0].date} to ${bs.at(-1).date}` });
  lines('#chCoh', [['mangrove', GREEN], ['land', LAND], ['water', WATERC]].map(([k, color]) => ({ color, pts: [[day(bs[0].date), null], ...co.filter((d) => d.days === 12).map((d) => [day(d.mid), d[k]]), [day(bs.at(-1).date), null]] })), { y0: 0, y1: 1, ticks: [0, 0.25, 0.5, 0.75, 1], xLabels: xl, label: 'NISAR 12-day coherence by surface' });
  $('#qcNote').textContent = `Gap: the pass of ${S.nisar_timeseries.qc_suspect_dates.join(', ')} looked identical and near zero everywhere, a sign of a faulty acquisition, so it is left out.`;
  const hv = ok.map((d) => d.mangrove_hv), cm = co.filter((d) => d.mangrove != null && d.days === 12);
  const rng = (rows) => { const v = rows.map((d) => d.mangrove); return `${Math.min(...v).toFixed(2)} to ${Math.max(...v).toFixed(2)}`; };
  const mon = (d) => +d.mid.slice(5, 7), yr = (d) => +d.mid.slice(0, 4);
  $('#f3').innerHTML = finding({
    measured: `Over ${ok.length} usable passes (${bs[0].date} to ${bs.at(-1).date}) the mangrove echo stayed between ${minus(Math.min(...hv).toFixed(1))} and ${minus(Math.max(...hv).toFixed(1))} dB, always far above open water and just below town and other land, where buildings echo strongly. Mangrove coherence was ${rng(cm.filter((d) => yr(d) === 2025 || mon(d) <= 3))} from late November to March, ${rng(cm.filter((d) => yr(d) === 2026 && mon(d) >= 5 && mon(d) <= 6))} in May and June, and ${rng(cm.filter((d) => yr(d) === 2026 && mon(d) >= 7))} from July to October. NISAR L-band, track 164, 80 m.`,
    maybe: 'The steady echo is consistent with a forest whose structure did not change this year. The early-summer dip in coherence could be wind, tides and moisture before the monsoon, or a change in how the data were acquired.',
    confidence: 'Low', why: 'One year only. We need a second year, at the same season, before calling anything a trend.',
  });

  // NISAR alerts (written by scripts/monitor/coastlens_monitor.py)
  const alerts = await fetch(import.meta.env.BASE_URL + 'data/alerts.json').then((r) => r.json());
  $('#flags').innerHTML = alerts.alerts.map((f) => `<article class="flag"><div><span class="mono">${f.title.split(':')[0]} · ${f.priority} priority</span><h3><em class="pink">${f.area_ha.toFixed(1)}</em> ha thinning</h3><span class="mono where">${f.lat.toFixed(3)}°N ${f.lon.toFixed(3)}°E${f.zone ? ` · decline zone ${f.zone}` : ''} · <a href="${f.maps_url}" target="_blank" rel="noopener">map ↗</a></span></div>
    ${finding({
      measured: `NISAR: ${f.observed} ${f.evidence}`,
      maybe: f.possible_causes.replace('To verify on the ground: ', ''),
      confidence: f.priority, why: `${f.confidence.replace(`${f.priority} (`, "").replace(").", ".")} NISAR checks again around ${alerts.next_nisar_pass}.`,
    })}</article>`).join('');

  compare(alerts.alerts);
});

/* ---------- side-by-side map of the real tile layers ---------- */
const LAYERS = [
  ['nisar_hv_20261011', 'NISAR radar (HV), 11 Oct 2026', 14],
  ['nisar_hv_20251121', 'NISAR radar (HV), 21 Nov 2025', 14],
  ['nisar_hh_20261011', 'NISAR radar (HH), 11 Oct 2026', 14],
  ['nisar_coh_20251214_20251226', 'NISAR coherence, 14–26 Dec 2025', 14],
  ['nisar_coh_20260904_20260916', 'NISAR coherence, 4–16 Sep 2026', 14],
  ['nisar_hv_change_20251121_20261011', 'NISAR HV change, Nov 2025 → Oct 2026', 14],
  ['nisar_ai_mangrove_2025_26', 'Mangrove mapped by NISAR alone (AI), 2025–26', 14],
  ['nisar_hv_trend_2025_26', 'NISAR forest watch: weakening vs strengthening', 14],
  ['gmw4_1985', 'Mangrove extent 1985 (GMW v4.1)', 14],
  ['gmw4_2025', 'Mangrove extent 2025 (GMW v4.1)', 14],
  ['gmw4_lossyear', 'Year each patch of mangrove was lost (GMW v4.1)', 14],
  ['alos_hv_2024', 'Older L-band radar (HV), 2024 (ALOS-2)', 14],
  ['l8_truecolor_2015_16', 'Photo, dry season 2015–16 (Landsat 8)', 14],
  ['l8_truecolor_2024_25', 'Photo, dry season 2024–25 (Landsat 8)', 14],
  ['s2_truecolor_2025_26', 'Sharper photo, 2025–26 (Sentinel-2)', 15],
  ['l8_ndvi_2015_16', 'Greenness (NDVI), 2015–16', 14],
  ['l8_ndvi_2024_25', 'Greenness (NDVI), 2024–25', 14],
  ['l8_ndvi_change_2015_16_to_2024_25', 'Greenness change, 2015–16 → 2024–25', 14],
];
const NOTES = {
  nisar_ai: 'Mangrove mapped from NISAR radar alone by our AI model (Random Forest), tested on areas it never saw. Darker green means more certain.',
  nisar_hv_trend: 'Each mangrove pixel compared with the whole forest over 27 passes. Red: weakening. Green: strengthening. One year of data only.',
  alos: 'ALOS-2 is the older L-band radar: same kind of image as NISAR, but one picture a year instead of every 12 days.',
  gmw4_lossyear: 'Each lost patch is coloured by the year it disappeared: yellow long ago, red recently.',
  nisar_hv: 'Radar: brighter means a stronger echo. Brightness also depends on tide and moisture, so a change is not proof of loss.',
  nisar_hh: 'HH radar is boosted where waves bounce off water and then tree trunks.',
  nisar_coh: 'Coherence: bright means the surface stayed the same for 12 days, dark means it changed.',
  gmw: 'Global Mangrove Watch is an external map. On the loss and gain layer, red is loss and blue is gain; differences include mapping error.',
  l8_ndvi: 'Greenness is not the same as mangrove extent. Farmland and algae are green too.',
  l8_truecolor: 'Photos are cloud-free composites. Tide differs between images.', s2: 'Photos are cloud-free composites. Tide differs between images.',
};
function compare(flags) {
  const [w, s, e, n] = BBOX, box = $('#cmp'), handle = $('#handle');
  const map = L.map('map', { scrollWheelZoom: false, minZoom: 9, maxZoom: 16, maxBounds: [[s - 0.6, w - 0.8], [n + 0.6, e + 0.8]] }).fitBounds([[s, w], [n, e]]);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Basemap: Esri, Maxar, Earthstar Geographics (reference only)', maxNativeZoom: 18, opacity: 0.55 }).addTo(map);
  L.rectangle([[s, w], [n, e]], { color: '#f4ede0', weight: 1, dashArray: '4 6', fill: false, interactive: false }).addTo(map);
  const side = {};
  ['L', 'R'].forEach((k, i) => {
    const pane = map.createPane('side' + k);
    pane.style.zIndex = 250 + i;
    const sel = $('#sel' + k);
    sel.innerHTML = LAYERS.map(([id, t]) => `<option value="${id}">${t}</option>`).join('');
    sel.value = k === 'L' ? 'l8_truecolor_2015_16' : 'nisar_hv_20261011';
    const set = () => {
      const [id, title, z] = LAYERS.find((l) => l[0] === sel.value);
      side[k]?.layer.remove();
      side[k] = { pane, layer: L.tileLayer(`${TILE_BASE}/${id}/{z}/{x}/{y}.png`, { pane: 'side' + k, maxNativeZoom: z, minNativeZoom: 10, bounds: [[s, w], [n, e]], attribution: 'Layers: CoastLens' }).addTo(map) };
      $('#lab' + k).textContent = title;
      const note = (id) => NOTES[Object.keys(NOTES).find((p) => id.startsWith(p))];
      $('#mapNote').textContent = [...new Set([note($('#selL').value), note($('#selR').value)])].join(' ');
    };
    sel.onchange = set;
    set();
  });
  flags.forEach((f) => L.circleMarker([f.lat, f.lon], { radius: 7, color: '#f4ede0', weight: 2, fillColor: '#f0566f', fillOpacity: 1 })
    .bindTooltip(`${f.title} · ${f.area_ha.toFixed(1)} ha · ${f.priority} priority`).addTo(map));
  let fx = 0.5;
  const clip = () => {
    const nw = map.containerPointToLayerPoint([0, 0]), se = map.containerPointToLayerPoint(map.getSize()), cx = nw.x + fx * map.getSize().x;
    side.L.pane.style.clip = `rect(${nw.y}px, ${cx}px, ${se.y}px, ${nw.x}px)`;
    side.R.pane.style.clip = `rect(${nw.y}px, ${se.x}px, ${se.y}px, ${cx}px)`;
    handle.style.left = fx * 100 + '%';
    handle.setAttribute('aria-valuenow', Math.round(fx * 100));
  };
  map.on('move zoom resize', clip);
  clip();
  let drag = false;
  const at = (e) => { const r = box.getBoundingClientRect(); fx = clamp((e.clientX - r.left) / r.width, 0.02, 0.98); clip(); };
  handle.addEventListener('pointerdown', (e) => { drag = true; handle.setPointerCapture(e.pointerId); });
  handle.addEventListener('pointermove', (e) => drag && at(e));
  handle.addEventListener('pointerup', () => (drag = false));
  handle.addEventListener('keydown', (e) => { if (e.key === 'ArrowLeft') fx = clamp(fx - 0.04, 0.02, 0.98); else if (e.key === 'ArrowRight') fx = clamp(fx + 0.04, 0.02, 0.98); else return; clip(); });
}
