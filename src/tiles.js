// Real CoastLens imagery. Tiles are loaded from the team's analysis site and
// stitched into one canvas per layer. Change TILE_BASE if the tiles move.
export const TILE_BASE = 'https://nasa-space-apps26-team-momos.vercel.app/tiles';
export const BBOX = [67.2, 23.8, 67.8, 24.3]; // west, south, east, north

const lon2x = (lon, z) => ((lon + 180) / 360) * 2 ** z;
const lat2y = (lat, z) => {
  const r = (lat * Math.PI) / 180;
  return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * 2 ** z;
};
const cache = new Map();

/**
 * Returns a canvas covering exactly the study box for one layer.
 * It fills in as tiles arrive; `m.loaded` counts tiles drawn so far.
 */
export function mosaic(layer, z = 12, bg = '#b9c6bf') {
  const key = layer + z;
  if (cache.has(key)) return cache.get(key);
  const [w, s, e, n] = BBOX;
  const x0 = lon2x(w, z), x1 = lon2x(e, z), y0 = lat2y(n, z), y1 = lat2y(s, z);
  const c = document.createElement('canvas');
  c.width = Math.round((x1 - x0) * 256);
  c.height = Math.round((y1 - y0) * 256);
  const g = c.getContext('2d');
  g.fillStyle = bg;
  g.fillRect(0, 0, c.width, c.height);
  c.loaded = 0;
  for (let tx = Math.floor(x0); tx <= Math.floor(x1); tx++) {
    for (let ty = Math.floor(y0); ty <= Math.floor(y1); ty++) {
      const img = new Image();
      img.decoding = 'async';
      img.onload = () => { g.drawImage(img, Math.round((tx - x0) * 256), Math.round((ty - y0) * 256)); c.loaded++; };
      img.src = `${TILE_BASE}/${layer}/${z}/${tx}/${ty}.png`;
    }
  }
  cache.set(key, c);
  return c;
}

/** drawImage with object-fit: cover. */
export function cover(g, img, w, h, zoom = 1, ox = 0, oy = 0) {
  const s = Math.max(w / img.width, h / img.height) * zoom;
  g.drawImage(img, (w - img.width * s) / 2 + ox, (h - img.height * s) / 2 + oy, img.width * s, img.height * s);
}

// --- illustrated cloud layer (procedural, clearly labelled as illustration) ---
function hash(x, y, s) {
  let h = Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263) + Math.imul(s | 0, 982451653);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}
function vnoise(x, y, s) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}
function fbm(x, y, s) {
  let t = 0, a = 0.5, f = 1;
  for (let i = 0; i < 4; i++) { t += a * vnoise(x * f, y * f, s + i * 17); a *= 0.5; f *= 2; }
  return t / 0.9375;
}
let cloudCanvas;
export function clouds() {
  if (cloudCanvas) return cloudCanvas;
  const W = 640, H = 420, c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d'), im = g.createImageData(W, H);
  for (let i = 0; i < W * H; i++) {
    const X = i % W, Y = (i / W) | 0;
    // wrap horizontally so the layer can scroll forever
    const k = X / W, n0 = (x) => fbm(x * 0.014, Y * 0.014, 31) * 0.7 + fbm(x * 0.045, Y * 0.045, 33) * 0.3;
    const n = n0(X) * (1 - k) + n0(X - W) * k;
    const a = Math.max(0, Math.min(1, (n - 0.3) * 3.6));
    im.data[i * 4] = 250; im.data[i * 4 + 1] = 245; im.data[i * 4 + 2] = 236; im.data[i * 4 + 3] = a * 255;
  }
  g.putImageData(im, 0, 0);
  return (cloudCanvas = c);
}
export function drawClouds(g, w, h, t, alpha = 1) {
  const c = clouds(), cw = Math.max(w, h * 1.6) * 1.3, off = (t * 14) % cw;
  g.save();
  g.globalAlpha = alpha;
  g.imageSmoothingEnabled = true;
  g.drawImage(c, -off, -h * 0.04, cw, h * 1.08);
  g.drawImage(c, cw - off, -h * 0.04, cw, h * 1.08);
  g.restore();
}
