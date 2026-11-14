// A small software-rendered 3D grey mangrove (Avicennia marina), shared by the
// home page ("What is a mangrove?") and the NISAR page (radar view).
// Stylised illustration, not a scan of a real tree.
import { DPR, REDUCE, clamp, fit } from './core.js';

const C = {
  mud: '#cdbfa3', mud2: '#c2b393', wood: '#5c4a3c', pneu: '#7d6753', water: 'rgba(160,182,176,.6)',
  leaves: [[92, 112, 74], [116, 134, 92], [74, 93, 58]], fish: '#6a584b', seed: '#8a9a5b',
  lband: '176,120,42', sband: '63,124,133', ink: '#3a2c24',
};

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => {
    s = Math.imul(s ^ (s >>> 15), 2246822507);
    s = Math.imul(s ^ (s >>> 13), 3266489909);
    s ^= s >>> 16;
    return (s >>> 0) / 4294967295;
  };
}

function buildTree() {
  const R = rng(42), segs = [], leaves = [], tips = [];
  const grow = (p, dir, len, w, d) => {
    const end = [p[0] + dir[0] * len, p[1] + dir[1] * len, p[2] + dir[2] * len];
    segs.push({ a: p, b: end, w });
    if (d >= 5) {
      tips.push(end);
      for (let i = 0; i < 3; i++) leaves.push({ p: [end[0] + (R() - 0.5) * 0.6, end[1] + (R() - 0.3) * 0.4, end[2] + (R() - 0.5) * 0.6], r: 0.32 + R() * 0.2, c: R() });
      return;
    }
    const n = d < 1 ? 3 : 2 + (R() < 0.45 ? 1 : 0);
    for (let i = 0; i < n; i++) {
      const az = R() * 6.283, tilt = 0.35 + R() * 0.45;
      let nd = [dir[0] + Math.cos(az) * tilt, dir[1] + 0.15, dir[2] + Math.sin(az) * tilt];
      const m = Math.hypot(...nd);
      nd = nd.map((v) => v / m);
      grow(end, nd, len * (0.7 + R() * 0.12), w * 0.62, d + 1);
    }
  };
  grow([0, 0, 0], [0, 1, 0], 1.25, 0.2, 0);
  const pn = [...Array(150)].map(() => {
    const a = R() * 6.283, rr = 0.5 + Math.pow(R(), 0.7) * 3.4;
    return { x: Math.cos(a) * rr, z: Math.sin(a) * rr, h: 0.14 + R() * 0.2 };
  });
  const seeds = tips.filter((_, i) => i % 6 === 0).slice(0, 8).map((t) => [t[0], t[1] - 0.25, t[2]]);
  const fish = [...Array(7)].map(() => ({ r: 1 + R() * 2.2, a: R() * 6.28, sp: 0.2 + R() * 0.3, y: 0.06 + R() * 0.12 }));
  return { segs, leaves, pn, seeds, fish, tips };
}
export const TREE = buildTree();
export const FOCUS = { roots: [1.4, 0.3, 0.9], leaf: [0.2, 3.3, 0], seed: TREE.seeds[0], fish: [-1.2, 0.15, -0.6] };

export function Tree3D(canvas, mode) {
  const x = canvas.getContext('2d');
  const st = { yaw: 0.6, tYaw: 0.6, auto: true, tgt: [0, 1.7, 0], cur: [0, 1.7, 0], dist: 9.5, tDist: 9.5, time: 0, tide: 0.6, band: 'L', pol: 'HV', focus: null };
  let drag = null;
  canvas.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, yaw: st.tYaw }; st.auto = false; canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e) => { if (drag) st.tYaw = drag.yaw - (e.clientX - drag.x) * 0.008; });
  canvas.addEventListener('pointerup', () => { drag = null; setTimeout(() => (st.auto = true), 2500); });
  const pitch = 0.18;

  function P(p) {
    const w = canvas.width, h = canvas.height;
    const X = p[0] - st.cur[0], Y = p[1] - st.cur[1], Z = p[2] - st.cur[2];
    const c = Math.cos(st.yaw), s = Math.sin(st.yaw);
    const x1 = X * c - Z * s, z1 = X * s + Z * c;
    const cp = Math.cos(pitch), sp = Math.sin(pitch);
    const y2 = Y * cp - z1 * sp;
    const z2 = Y * sp + z1 * cp + st.dist;
    if (z2 < 0.2) return null;
    const wide = w / DPR > 900;
    const f = h * (wide ? 1.25 : 0.95);
    const ox = wide ? (mode === 'radar' ? -w * 0.12 : w * 0.02) : 0;
    return { x: w / 2 + ox + (x1 / z2) * f, y: h * (wide ? 0.58 : 0.52) - (y2 / z2) * f, z: z2, s: f / z2 };
  }

  function disc(rad, y, fill) {
    x.beginPath();
    for (let i = 0; i <= 48; i++) {
      const a = (i / 48) * 6.283, p = P([Math.cos(a) * rad, y, Math.sin(a) * rad]);
      if (!p) continue;
      i ? x.lineTo(p.x, p.y) : x.moveTo(p.x, p.y);
    }
    x.fillStyle = fill;
    x.fill();
  }
  const stroke = (a, b, col, lw) => { x.strokeStyle = col; x.lineWidth = lw; x.beginPath(); x.moveTo(a.x, a.y); x.lineTo(b.x, b.y); x.stroke(); };

  function draw() {
    fit(canvas);
    const w = canvas.width, h = canvas.height;
    st.time += REDUCE ? 0 : 0.016;
    if (st.auto && !REDUCE) st.tYaw += 0.002;
    st.yaw += (st.tYaw - st.yaw) * 0.07;
    for (let i = 0; i < 3; i++) st.cur[i] += ((st.focus || st.tgt)[i] - st.cur[i]) * 0.05;
    st.dist += ((st.focus ? 5.2 : st.tDist) - st.dist) * 0.05;
    x.clearRect(0, 0, w, h);
    x.lineCap = 'round';
    const radar = mode === 'radar', L = st.band === 'L', HV = st.pol === 'HV';
    const wl = radar ? st.tide * 0.45 : 0.18 + 0.08 * Math.sin(st.time * 0.5);

    disc(5.2, 0, C.mud);
    disc(4.2, 0, C.mud2);
    for (const q of TREE.pn) {
      if (q.h >= wl) continue;
      const a = P([q.x, 0, q.z]), b = P([q.x, q.h, q.z]);
      if (a && b) stroke(a, b, 'rgba(110,90,72,.5)', Math.max(1, 0.04 * a.s));
    }
    if (!radar) {
      for (const f of TREE.fish) {
        f.a += f.sp * 0.016 * (REDUCE ? 0 : 1);
        const p = P([Math.cos(f.a) * f.r, Math.min(f.y, wl - 0.02), Math.sin(f.a) * f.r]);
        if (!p) continue;
        x.fillStyle = C.fish;
        x.beginPath(); x.ellipse(p.x, p.y, 0.14 * p.s, 0.06 * p.s, 0, 0, 7); x.fill();
      }
    }
    disc(5.4, wl, radar && !HV && L ? `rgba(${C.lband},${0.18 + 0.3 * st.tide})` : C.water);

    const items = [];
    for (const q of TREE.pn) {
      if (q.h < wl) continue;
      const a = P([q.x, wl, q.z]), b = P([q.x, q.h, q.z]);
      if (a && b) items.push({ z: a.z, k: 0, a, b });
    }
    for (const sg of TREE.segs) {
      const a = P(sg.a), b = P(sg.b);
      if (a && b) items.push({ z: (a.z + b.z) / 2, k: 1, a, b, w: sg.w });
    }
    for (const l of TREE.leaves) { const p = P(l.p); if (p) items.push({ z: p.z, k: 2, p, r: l.r, c: l.c }); }
    if (!radar) for (const s of TREE.seeds) { const p = P(s); if (p) items.push({ z: p.z - 0.01, k: 3, p }); }
    items.sort((a, b) => b.z - a.z);

    const woodGlow = radar && L && HV, leafGlow = radar && !L;
    for (const it of items) {
      if (it.k === 0) stroke(it.a, it.b, C.pneu, Math.max(1, 0.045 * it.a.s));
      else if (it.k === 1) {
        stroke(it.a, it.b, woodGlow ? `rgb(${C.lband})` : C.wood, Math.max(1.2, it.w * it.a.s));
        if (woodGlow) stroke(it.a, it.b, `rgba(${C.lband},.22)`, Math.max(4, it.w * it.a.s * 2.6));
      } else if (it.k === 2) {
        const sh = clamp(1.1 - (it.z - st.dist) / 6, 0.75, 1.15);
        let col = C.leaves[it.c < 0.33 ? 0 : it.c < 0.66 ? 1 : 2].map((v) => Math.round(v * sh));
        if (leafGlow) col = col.map((v, i) => Math.round(v * 0.45 + [63, 124, 133][i] * 0.75));
        x.globalAlpha = radar && L ? 0.3 : 0.94;
        x.fillStyle = `rgb(${col})`;
        x.beginPath(); x.arc(it.p.x, it.p.y, it.r * it.p.s, 0, 7); x.fill();
        x.globalAlpha = 1;
        if (!radar && st.focus === FOCUS.leaf && it.c > 0.7) { x.fillStyle = '#fff'; x.fillRect(it.p.x - it.r * it.p.s * 0.3, it.p.y - it.r * it.p.s * 0.2, 2.5 * DPR, 2.5 * DPR); }
      } else { x.fillStyle = C.seed; x.beginPath(); x.ellipse(it.p.x, it.p.y, 0.07 * it.p.s, 0.11 * it.p.s, 0, 0, 7); x.fill(); }
    }
    if (!radar && st.focus === FOCUS.roots) {
      for (let i = 0; i < 14; i++) {
        const q = TREE.pn[i * 7], b = P([q.x, q.h + ((st.time * 0.4 + i * 0.13) % 1) * 0.6, q.z]);
        if (b) { x.fillStyle = 'rgba(255,255,255,.9)'; x.beginPath(); x.arc(b.x, b.y, 3 * DPR, 0, 7); x.fill(); }
      }
    }
    if (radar) rays(wl);
    return P;
  }

  // radar pulses travelling from the satellite, and the echoes coming back
  function rays(wl) {
    const w = canvas.width, wide = w / DPR > 900;
    const sat = { x: w * (wide ? 0.6 : 0.82), y: (wide ? 120 : 150) * DPR };
    x.save();
    x.fillStyle = C.ink;
    x.fillRect(sat.x - 10 * DPR, sat.y - 8 * DPR, 20 * DPR, 16 * DPR);
    x.fillStyle = '#8f7f6c';
    x.fillRect(sat.x - 40 * DPR, sat.y - 4 * DPR, 26 * DPR, 8 * DPR);
    x.fillRect(sat.x + 14 * DPR, sat.y - 4 * DPR, 26 * DPR, 8 * DPR);
    x.font = `500 ${10 * DPR}px "Geist Mono", monospace`;
    x.fillStyle = C.ink;
    x.fillText('NISAR', sat.x - 18 * DPR, sat.y - 16 * DPR);
    const L = st.band === 'L', col = L ? C.lband : C.sband;
    const dash = () => x.setLineDash([10 * DPR, 12 * DPR]), dots = () => x.setLineDash([3 * DPR, 6 * DPR]);
    dash();
    x.lineDashOffset = -st.time * 60 * DPR;
    const line = (a, b, al, lw = 2.5) => stroke(a, b, `rgba(${col},${al})`, lw * DPR);
    if (!L) {
      [0, 5, 11, 17].forEach((ti, i) => {
        const p = P(TREE.tips[(ti * 3) % TREE.tips.length]);
        if (!p) return;
        line(sat, p, 0.9);
        dots();
        [[-1, -0.6], [1, -0.4], [0.5, 0.8]].forEach(([dx, dy]) => line(p, { x: p.x + dx * 50 * DPR, y: p.y + dy * 50 * DPR }, 0.6, 1.5));
        dash();
        if (i < 2) line(p, sat, 0.35);
      });
    } else if (st.pol === 'HV') {
      [[0, 1.2, 0], [0.3, 2.2, 0.2], [-0.4, 2.6, -0.3], [0.6, 3, 0.1]].forEach((q) => { const p = P(q); if (p) { line(sat, p, 0.9); line(p, sat, 0.45); } });
    } else {
      [[0.9, 0, 0.3], [-0.8, 0, 0.6], [0.4, 0, -0.9]].forEach((q) => {
        const wp = P([q[0], wl, q[2]]), tp = P([q[0] * 0.12, wl + 0.6, q[2] * 0.12]);
        if (!wp || !tp) return;
        line(sat, wp, 0.9);
        if (st.tide > 0.3) { line(wp, tp, 0.9); line(tp, sat, 0.3 + 0.6 * st.tide, 1.5 + 3 * st.tide); }
        else { dots(); line(wp, { x: wp.x - 40 * DPR, y: wp.y - 12 * DPR }, 0.6, 1.5); line(wp, { x: wp.x + 40 * DPR, y: wp.y - 16 * DPR }, 0.6, 1.5); dash(); }
      });
    }
    x.restore();
  }
  return { st, draw };
}
