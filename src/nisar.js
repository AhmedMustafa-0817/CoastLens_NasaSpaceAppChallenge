import { init, REDUCE, DPR, $, $$, clamp, lerp, fit, whileVisible, loadStats } from './core.js';
import { mosaic, cover, drawClouds } from './tiles.js';
import { Tree3D } from './tree3d.js';

init();
const SAND = '#f4ede0', MOCHA = '#3a2c24', SOFT = '#6a584b', L = '176,120,42', GREEN = '#4a5d3a', WATER = '#b9c6bf';
const optical = () => mosaic('s2_truecolor_2025_26'), radarImg = () => mosaic('nisar_hv_20261010', 12, '#141210');
const mono = (g, px) => (g.font = `500 ${px * DPR}px "Geist Mono", monospace`);

function satellite(g, x, y, s = 1) {
  g.fillStyle = MOCHA; g.fillRect(x - 11 * s, y - 8 * s, 22 * s, 16 * s);
  g.fillStyle = '#8f7f6c'; g.fillRect(x - 42 * s, y - 4 * s, 27 * s, 8 * s); g.fillRect(x + 15 * s, y - 4 * s, 27 * s, 8 * s);
}

/* ---------- 01 · camera vs radar, in day, night and cloud ---------- */
{
  const c = $('#cPulse'), g = c.getContext('2d');
  let sky = 'day', t = 0, dark = 0, cloud = 0;
  $$('[data-sky]').forEach((b) => (b.onclick = () => { sky = b.dataset.sky; $$('[data-sky]').forEach((o) => o.setAttribute('aria-pressed', o === b)); }));
  whileVisible(c, () => {
    fit(c);
    const w = c.width, h = c.height, u = DPR;
    t += REDUCE ? 0 : 0.016;
    dark = lerp(dark, sky === 'night' ? 1 : 0, 0.05); cloud = lerp(cloud, sky === 'cloud' ? 1 : 0, 0.05);
    g.fillStyle = `rgb(${lerp(244, 40, dark)},${lerp(237, 31, dark)},${lerp(224, 27, dark)})`; g.fillRect(0, 0, w, h);
    const ink = dark > 0.5 ? SAND : MOCHA, gy = h * 0.6;
    // ground: water, mudflat, a line of mangroves
    g.fillStyle = WATER; g.globalAlpha = 1 - dark * 0.6; g.fillRect(0, gy, w, h - gy);
    g.fillStyle = '#cdbfa3'; g.beginPath(); g.moveTo(w * 0.2, h); g.quadraticCurveTo(w * 0.5, gy - (h - gy) * 1.05, w * 0.84, h); g.fill();
    g.fillStyle = GREEN; for (let i = 0; i < 11; i++) { g.beginPath(); g.arc(w * (0.33 + i * 0.035), gy - (2 + (i % 3) * 5) * u, 13 * u, 0, 7); g.fill(); }
    g.globalAlpha = 1;
    const cam = { x: w * 0.27, y: h * 0.16 }, rad = { x: w * 0.73, y: h * 0.16 }, cy = h * 0.5;
    // camera: a cone of sight that needs light and clear air
    const sees = 1 - Math.max(dark, cloud);
    g.fillStyle = `rgba(106,88,75,${0.06 + 0.12 * sees})`; g.beginPath(); g.moveTo(cam.x, cam.y); g.lineTo(cam.x - 70 * u, lerp(gy, cy, cloud)); g.lineTo(cam.x + 70 * u, lerp(gy, cy, cloud)); g.fill();
    // radar: pulses down (solid), echoes up (dashed)
    for (let k = 0; k < 4; k++) {
      const p = (t * 0.35 + k / 4) % 1, down = p < 0.5, q = down ? p * 2 : (p - 0.5) * 2, y = down ? lerp(rad.y, gy, q) : lerp(gy, rad.y, q), wd = lerp(8, 70, down ? q : 1 - q) * u;
      g.strokeStyle = `rgba(${L},${down ? 0.9 : 0.55})`; g.lineWidth = 2.5 * u; g.setLineDash(down ? [] : [5 * u, 6 * u]);
      g.beginPath(); g.moveTo(rad.x - wd, y); g.quadraticCurveTo(rad.x, y + (down ? 12 : -12) * u, rad.x + wd, y); g.stroke();
    }
    g.setLineDash([]);
    if (cloud > 0.01) { g.save(); g.beginPath(); g.rect(0, cy - 44 * u, w, 88 * u); g.clip(); drawClouds(g, w, h, t * 2, cloud); g.fillStyle = `rgba(250,245,236,${0.55 * cloud})`; g.fillRect(0, cy - 26 * u, w, 52 * u); g.restore(); }
    satellite(g, cam.x, cam.y, u); satellite(g, rad.x, rad.y, u);
    mono(g, 10); g.fillStyle = ink; g.textAlign = 'center';
    g.fillText('CAMERA', cam.x, cam.y - 20 * u); g.fillText('RADAR · NISAR', rad.x, rad.y - 20 * u);
    // what each one gets: thumbnails cut from the real images
    const tw = Math.min(w * 0.3, 190 * u), th = tw * 0.62, ty = h - th - 16 * u;
    [[cam.x, optical(), sees], [rad.x, radarImg(), 1]].forEach(([x, img, a], i) => {
      g.save(); g.beginPath(); g.rect(x - tw / 2, ty, tw, th); g.clip();
      g.fillStyle = i ? '#141210' : dark > cloud ? '#141210' : '#f2ede4'; g.fillRect(x - tw / 2, ty, tw, th);
      g.globalAlpha = a; g.translate(x - tw / 2, ty); cover(g, img, tw, th, 1.6); g.restore();
      g.strokeStyle = SAND; g.lineWidth = 3 * u; g.strokeRect(x - tw / 2, ty, tw, th);
    });
    g.fillStyle = ink;
    g.fillText(sees > 0.5 ? 'SEES THE COAST' : sky === 'night' ? 'NO LIGHT · NO PICTURE' : 'CLOUD · NO PICTURE', cam.x, ty - 10 * u);
    g.fillText('SEES THE COAST', rad.x, ty - 10 * u);
    g.textAlign = 'left';
  });
}

/* ---------- 02 · how much comes back: water, land, mangrove ---------- */
loadStats().then((S) => {
  const row = S.nisar_timeseries.backscatter.series.at(-1);
  const cols = [
    { name: 'OPEN WATER', db: row.water_hv, back: 1, kind: 0 },
    { name: 'OTHER LAND', db: row.land_hv, back: 3, kind: 1 },
    { name: 'MANGROVE', db: row.mangrove_hv, back: 6, kind: 2 },
  ];
  const c = $('#cEcho'), g = c.getContext('2d');
  let t = 0;
  whileVisible(c, () => {
    fit(c);
    const w = c.width, h = c.height, u = DPR, gy = h * 0.6;
    t += REDUCE ? 0.4 : 0.016;
    g.clearRect(0, 0, w, h);
    cols.forEach((col, i) => {
      const x = w * (0.18 + i * 0.32), cw = w * 0.24;
      g.fillStyle = ['#8fa39c', '#cdbfa3', '#cdbfa3'][col.kind]; g.fillRect(x - cw / 2, gy, cw, 10 * u);
      if (col.kind === 2) { g.strokeStyle = '#8a7462'; g.lineWidth = 3 * u; g.fillStyle = '#7d8f63'; for (let k = -3; k <= 3; k++) { const tx = x + k * cw * 0.13, th = (34 + ((k * 7) % 11)) * u; g.beginPath(); g.moveTo(tx, gy); g.lineTo(tx, gy - th); g.stroke(); g.beginPath(); g.arc(tx, gy - th, 13 * u, 0, 7); g.fill(); } }
      satellite(g, x, 30 * u, u * 0.8);
      const p = (t * 0.3 + i * 0.22) % 1;
      // one pulse goes down
      if (p < 0.5) { const y = lerp(44 * u, gy - 6 * u, p * 2); g.fillStyle = `rgb(${L})`; g.beginPath(); g.arc(x, y, 5 * u, 0, 7); g.fill(); }
      else { // echoes return: few from water (most bounce away), many from forest
        const q = (p - 0.5) * 2;
        for (let k = 0; k < 6; k++) {
          const home = k < col.back, a = home ? -Math.PI / 2 + (k - (col.back - 1) / 2) * 0.09 : (k % 2 ? -0.35 : -2.8) + k * 0.05;
          const d = q * (home ? gy - 50 * u : w * 0.2);
          g.fillStyle = `rgba(${L},${home ? 0.9 : 0.3 * (1 - q)})`; g.beginPath(); g.arc(x + Math.cos(a) * d, gy - 6 * u + Math.sin(a) * d, 3 * u, 0, 7); g.fill();
        }
      }
      // measured bar: -28 dB (dark) to -10 dB (bright)
      const k = clamp((col.db + 28) / 18, 0, 1), by = h * 0.78, bh = 14 * u;
      g.fillStyle = 'rgba(244,237,224,.14)'; g.fillRect(x - cw / 2, by, cw, bh);
      g.fillStyle = `rgb(${L})`; g.fillRect(x - cw / 2, by, cw * k, bh);
      mono(g, 10); g.fillStyle = SAND; g.textAlign = 'center';
      g.fillText(col.name, x, by - 12 * u);
      g.font = `400 ${26 * u}px "Instrument Serif", serif`; g.fillText(`${col.db.toFixed(1).replace('-', '−')} dB`, x, by + bh + 34 * u);
    });
    g.textAlign = 'left';
  });

  /* ---------- 05 · every 12 days: orbit + the real list of passes ---------- */
  const passes = S.nisar_timeseries.backscatter.series, bad = S.nisar_timeseries.qc_suspect_dates;
  const strip = $('#passes');
  strip.innerHTML = passes.map((p) => `<i class="${bad.includes(p.date) ? 'bad' : ''}" title="${p.date}"></i>`).join('');
  strip.setAttribute('aria-label', `${passes.length} NISAR passes over Keti Bandar, ${passes[0].date} to ${passes.at(-1).date}`);
  const bars = $$('i', strip), note = $('#passNote');
  const o = $('#cOrbit'), og = o.getContext('2d');
  let ot = 0, shown = -1;
  whileVisible(o, () => {
    fit(o);
    const w = o.width, h = o.height, u = DPR, cx = w / 2, cy = h * 0.52, R = Math.min(w, h) * 0.3;
    ot += REDUCE ? 0 : 0.016;
    const n = REDUCE ? passes.length - 1 : Math.floor(ot / 1.1) % (passes.length + 3), idx = Math.min(n, passes.length - 1);
    if (idx !== shown) {
      shown = idx;
      bars.forEach((b, i) => b.classList.toggle('on', i <= idx));
      const p = passes[idx];
      note.textContent = `Pass ${idx + 1} of ${passes.length} · ${p.date}${bad.includes(p.date) ? ' · faulty pass, left out of our charts' : ''}`;
    }
    og.clearRect(0, 0, w, h);
    // the Earth, turning
    og.fillStyle = '#eadfcb'; og.beginPath(); og.arc(cx, cy, R, 0, 7); og.fill();
    og.save(); og.beginPath(); og.arc(cx, cy, R, 0, 7); og.clip();
    og.strokeStyle = 'rgba(58,44,36,.16)'; og.lineWidth = u;
    for (let k = 0; k < 8; k++) { const a = ((ot * 0.15 + k / 8) % 1) * Math.PI, rx = Math.abs(Math.cos(a)) * R; og.beginPath(); og.ellipse(cx, cy, rx, R, 0, 0, 7); og.stroke(); }
    for (let k = -2; k <= 2; k++) { og.beginPath(); og.ellipse(cx, cy + k * R * 0.3, Math.sqrt(1 - (k * 0.3) ** 2) * R, R * 0.05, 0, 0, 7); og.stroke(); }
    og.restore();
    // near-polar orbit, and the satellite on it
    og.strokeStyle = 'rgba(58,44,36,.35)'; og.setLineDash([4 * u, 7 * u]);
    og.beginPath(); og.ellipse(cx, cy, R * 0.34, R * 1.38, 0.16, 0, 7); og.stroke(); og.setLineDash([]);
    const a = ot * 1.4, sx = cx + Math.cos(a) * R * 0.34 * Math.cos(0.16) - Math.sin(a) * R * 1.38 * Math.sin(0.16), sy = cy + Math.cos(a) * R * 0.34 * Math.sin(0.16) + Math.sin(a) * R * 1.38 * Math.cos(0.16);
    // Keti Bandar, about 24°N
    const kx = cx + R * 0.2, ky = cy - R * 0.4, pulse = (ot / 1.1) % 1;
    og.strokeStyle = `rgba(${L},${1 - pulse})`; og.lineWidth = 2 * u; og.beginPath(); og.arc(kx, ky, pulse * 34 * u, 0, 7); og.stroke();
    og.fillStyle = '#f0566f'; og.beginPath(); og.arc(kx, ky, 5 * u, 0, 7); og.fill();
    satellite(og, sx, sy, u * 0.7);
    mono(og, 10); og.fillStyle = MOCHA; og.fillText('KETI BANDAR', kx + 12 * u, ky + 4 * u);
    og.fillStyle = SOFT; og.textAlign = 'center'; og.fillText('ORBIT NOT TO SCALE', cx, h - 16 * u); og.textAlign = 'left';
  });
});

/* ---------- 03 · the radar tree ---------- */
{
  const tree = Tree3D($('#cRadar'), 'radar');
  tree.st.tDist = 10.5; tree.st.tide = 0.7;
  const upd = () => {
    const s = tree.st, isL = s.band === 'L', HV = s.pol === 'HV';
    $$('[data-b]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.b === s.band));
    $$('[data-p]').forEach((b) => b.setAttribute('aria-pressed', b.dataset.p === s.pol));
    const e = !isL ? (HV ? 0.42 : 0.55) : HV ? 0.6 + 0.1 * s.tide : 0.2 + 0.72 * s.tide;
    $('#echo').style.width = e * 100 + '%';
    $('#echo').style.background = isL ? 'var(--lband)' : 'var(--sband)';
    $('#sNote').hidden = isL;
    $('#rtext').innerHTML = !isL
      ? '<b>S-band</b> waves are short, about 9 cm. They mostly bounce off the <b>leaves on top</b> and say little about the trunks below.'
      : HV
        ? '<b>L-band, HV.</b> Waves about 24 cm long slip past the leaves and scatter around <b>trunks and branches</b>. More wood, more echo.'
        : s.tide > 0.3
          ? '<b>L-band, HH.</b> The water is a mirror. A wave bounces off it, hits a trunk and returns: the bright <b>“double bounce”</b> of a flooded forest.'
          : '<b>L-band, HH, low tide.</b> No water mirror, so the echo drops. The forest did not change, the tide did. This is why one bright or dark image proves nothing.';
  };
  $$('[data-b]').forEach((b) => (b.onclick = () => { tree.st.band = b.dataset.b; upd(); }));
  $$('[data-p]').forEach((b) => (b.onclick = () => { tree.st.pol = b.dataset.p; upd(); }));
  $('#tide').oninput = (e) => { tree.st.tide = e.target.value / 100; upd(); };
  upd();
  whileVisible($('#radar-tree'), tree.draw);
}

/* ---------- 04 · the real image: photo vs radar ---------- */
{
  const c = $('#cReal'), g = c.getContext('2d');
  let fx = 0.5, tfx = 0.5, touched = false, t = 0;
  const set = (e) => { const r = c.getBoundingClientRect(); tfx = clamp((e.clientX - r.left) / r.width, 0.03, 0.97); touched = true; };
  c.addEventListener('pointermove', set); c.addEventListener('pointerdown', set);
  whileVisible(c, () => {
    fit(c);
    const w = c.width, h = c.height, u = DPR;
    t += REDUCE ? 0 : 0.016;
    if (!touched) tfx = 0.5 + 0.22 * Math.sin(t * 0.5);
    fx = lerp(fx, tfx, 0.1);
    g.imageSmoothingEnabled = true;
    cover(g, optical(), w, h, 1.15);
    g.save(); g.beginPath(); g.rect(fx * w, 0, w, h); g.clip(); cover(g, radarImg(), w, h, 1.15); g.restore();
    g.fillStyle = SAND; g.fillRect(fx * w - u, 0, 2 * u, h);
    g.beginPath(); g.arc(fx * w, h / 2, 20 * u, 0, 7); g.fill();
    mono(g, 10);
    const tagAt = (txt, x, right) => { const tw = g.measureText(txt).width + 16 * u, bx = right ? x - tw : x; g.fillStyle = SAND; g.fillRect(bx, 12 * u, tw, 24 * u); g.fillStyle = MOCHA; g.fillText(txt, bx + 8 * u, 28 * u); };
    tagAt('PHOTO · SENTINEL-2', 12 * u, false); tagAt('RADAR · NISAR', w - 12 * u, true);
  });
}
