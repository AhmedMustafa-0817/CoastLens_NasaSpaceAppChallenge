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

loadStats().then((S) => {
  const ch = S.mangrove_change, ar = S.mangrove_area.years, a0 = ar[0].km2, a1 = ar.at(-1).km2;
  $('#stats4').innerHTML = [
    [`<em class="pink">${f1(ch.loss_km2)}</em>`, `km² mapped as lost (${f1((ch.loss_km2 / a0) * 100)}% of ${ch.from})`],
    [f1(ch.gain_km2), `km² mapped as gained (${f1((ch.gain_km2 / a0) * 100)}%)`],
    [f1(ch.stable_km2), 'km² unchanged'],
    [`${ch.from}–${String(ch.to).slice(2)}`, 'Global Mangrove Watch v3 maps'],
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
    measured: `Mangrove was mapped on ${f1(a0)} km² in ${ar[0].year} and ${f1(a1)} km² in ${ar.at(-1).year}: a net fall of ${f1(a0 - a1)} km² (${f1(((a0 - a1) / a0) * 100)}%). Source: Global Mangrove Watch v3, about 25 m, area computed by CoastLens.`,
    maybe: 'Real loss, for example creek-bank erosion, cutting for fuel and fodder, grazing, or less fresh water reaching the delta. Some of it may also be a difference between how the 1996 and 2020 maps were made.',
    confidence: 'Medium', why: 'One external map product. The figure includes mapping error and has not been checked in the field.',
  });

  // 02 NDVI
  const nd = S.ndvi_in_mangroves.series, s1 = S.s1_vh_in_mangroves.series;
  lines('#chNdvi', [{ color: '#4a5d3a', pts: nd.map((d, i) => [i, d.mean]) }], { y0: 0.28, y1: 0.42, ticks: [0.3, 0.34, 0.38, 0.42], xLabels: nd.map((d, i) => [i, d.season]), label: 'Mean NDVI inside mangroves: ' + nd.map((d) => `${d.season}: ${d.mean}`).join(', ') });
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
    measured: `Over ${ok.length} usable passes (${bs[0].date} to ${bs.at(-1).date}) the mangrove echo stayed between ${minus(Math.min(...hv).toFixed(1))} and ${minus(Math.max(...hv).toFixed(1))} dB, always well above land and water. Mangrove coherence was ${rng(cm.filter((d) => yr(d) === 2025 || mon(d) <= 3))} from late November to March, ${rng(cm.filter((d) => yr(d) === 2026 && mon(d) >= 5 && mon(d) <= 6))} in May and June, and ${rng(cm.filter((d) => yr(d) === 2026 && mon(d) >= 7))} from July to October. NISAR L-band, track 164, 80 m.`,
    maybe: 'The steady echo is consistent with a forest whose structure did not change this year. The early-summer dip in coherence could be wind, tides and moisture before the monsoon, or a change in how the data were acquired.',
    confidence: 'Low', why: 'One year only. We need a second year, at the same season, before calling anything a trend.',
  });

  // flags
  $('#flags').innerHTML = S.flags.map((f) => {
    const loss = f.kind === 'loss';
    return `<article class="flag"><div><span class="mono">${loss ? 'Mapped loss' : 'Mapped gain'}</span><h3>${loss ? `<em class="pink">−${f.gmw_loss.toFixed(2)}</em>` : `<em class="green" style="font-style:normal">+${f.gmw_gain.toFixed(2)}</em>`} km²</h3><span class="mono where">${f.lat.toFixed(3)}°N ${f.lon.toFixed(3)}°E · 1 km square</span></div>
    ${finding({
      measured: `${loss ? `${f.gmw_loss.toFixed(2)} km² mapped as mangrove in 1996 but not in 2020.` : `${f.gmw_gain.toFixed(2)} km² mapped as mangrove in 2020 but not in 1996.`} Greenness change 2015–16 to 2024–25: +${f.ndvi.toFixed(3)}. NISAR HV change Nov 2025 to Oct 2026, relative to the whole landscape: ${f.hv >= 0 ? '+' : '−'}${Math.abs(f.hv).toFixed(1)} dB. 12-day coherence, Dec 2025: ${f.coh.toFixed(2)}.`,
      maybe: loss ? 'Newer sensors do not show decline here, so this may be regrowth after 2020, or a difference between the two maps. Erosion, cutting or grazing before 2020 are also possible.' : 'Restoration planting, natural spread onto new mudflats, or a difference between the two maps.',
      confidence: f.confidence, why: `${f.agree} independent indicators agree. Not field-verified.`,
    })}</article>`;
  }).join('');

  compare(S.flags);
});

/* ---------- side-by-side map of the real tile layers ---------- */
const LAYERS = [
  ['nisar_hv_20261010', 'NISAR radar (HV), 10 Oct 2026', 13],
  ['nisar_hv_20251120', 'NISAR radar (HV), 20 Nov 2025', 13],
  ['nisar_hh_20261010', 'NISAR radar (HH), 10 Oct 2026', 13],
  ['nisar_coh_20251214_20251226', 'NISAR coherence, 14–26 Dec 2025', 13],
  ['nisar_coh_20260904_20260916', 'NISAR coherence, 4–16 Sep 2026', 13],
  ['nisar_hv_change_20251120_20261010', 'NISAR HV change, Nov 2025 → Oct 2026', 12],
  ['gmw_1996', 'Mangrove extent 1996 (GMW)', 13],
  ['gmw_2020', 'Mangrove extent 2020 (GMW)', 13],
  ['gmw_lossgain_1996_2020', 'Mangrove loss and gain, 1996 → 2020', 13],
  ['l8_truecolor_2015_16', 'Photo, dry season 2015–16 (Landsat 8)', 13],
  ['l8_truecolor_2024_25', 'Photo, dry season 2024–25 (Landsat 8)', 13],
  ['s2_truecolor_2025_26', 'Sharper photo, 2025–26 (Sentinel-2)', 14],
  ['l8_ndvi_2015_16', 'Greenness (NDVI), 2015–16', 13],
  ['l8_ndvi_2024_25', 'Greenness (NDVI), 2024–25', 13],
  ['l8_ndvi_change_2015_16_to_2024_25', 'Greenness change, 2015–16 → 2024–25', 13],
];
const NOTES = {
  nisar_hv: 'Radar: brighter means a stronger echo. Brightness also depends on tide and moisture, so a change is not proof of loss.',
  nisar_hh: 'HH radar is boosted where waves bounce off water and then tree trunks.',
  nisar_coh: 'Coherence: bright means the surface stayed the same for 12 days, dark means it changed.',
  gmw: 'Global Mangrove Watch is an external map. On the loss and gain layer, red is loss and blue is gain; differences include mapping error.',
  l8_ndvi: 'Greenness is not the same as mangrove extent. Farmland and algae are green too.',
  l8_truecolor: 'Photos are cloud-free composites. Tide differs between images.', s2: 'Photos are cloud-free composites. Tide differs between images.',
};
function compare(flags) {
  const [w, s, e, n] = BBOX, box = $('#cmp'), handle = $('#handle');
  const map = L.map('map', { scrollWheelZoom: false, minZoom: 9, maxZoom: 14, maxBounds: [[s - 0.6, w - 0.8], [n + 0.6, e + 0.8]] }).fitBounds([[s, w], [n, e]]);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Basemap: Esri, Maxar, Earthstar Geographics (reference only)', maxNativeZoom: 18, opacity: 0.55 }).addTo(map);
  L.rectangle([[s, w], [n, e]], { color: '#f4ede0', weight: 1, dashArray: '4 6', fill: false, interactive: false }).addTo(map);
  const side = {};
  ['L', 'R'].forEach((k, i) => {
    const pane = map.createPane('side' + k);
    pane.style.zIndex = 250 + i;
    const sel = $('#sel' + k);
    sel.innerHTML = LAYERS.map(([id, t]) => `<option value="${id}">${t}</option>`).join('');
    sel.value = k === 'L' ? 'l8_truecolor_2015_16' : 'nisar_hv_20261010';
    const set = () => {
      const [id, title, z] = LAYERS.find((l) => l[0] === sel.value);
      side[k]?.layer.remove();
      side[k] = { pane, layer: L.tileLayer(`${TILE_BASE}/${id}/{z}/{x}/{y}.png`, { pane: 'side' + k, maxNativeZoom: z, minNativeZoom: 9, bounds: [[s, w], [n, e]], attribution: 'Layers: CoastLens' }).addTo(map) };
      $('#lab' + k).textContent = title;
      const note = (id) => NOTES[Object.keys(NOTES).find((p) => id.startsWith(p))];
      $('#mapNote').textContent = [...new Set([note($('#selL').value), note($('#selR').value)])].join(' ');
    };
    sel.onchange = set;
    set();
  });
  flags.forEach((f) => L.circleMarker([f.lat, f.lon], { radius: 7, color: '#f4ede0', weight: 2, fillColor: f.kind === 'loss' ? '#f0566f' : '#4a5d3a', fillOpacity: 1 })
    .bindTooltip(`${f.kind === 'loss' ? 'Mapped loss' : 'Mapped gain'} · ${(f.kind === 'loss' ? f.gmw_loss : f.gmw_gain).toFixed(2)} km² · ${f.confidence} confidence`).addTo(map));
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
