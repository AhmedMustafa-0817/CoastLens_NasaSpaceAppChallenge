"""Find the parts of the study box where mangroves have been declining steadily for years (GMW v4.1, 1985-2025).

    python scripts/analysis/gmw_decline_zones.py data_raw/gmw_v4/gmw_mng_ext_v4112_stack/GMW_N25E067_v4112_mng_ext.tif

How it works
  1. The box is cut into ~250 m cells and the mangrove area of every cell is measured for all 41 years.
  2. A cell is "steadily declining" when, after its peak year (<= 2018), it lost >= 40 % of its peak forest,
     the years after the peak mostly go down (Kendall tau <= -0.5) and it has not recovered in the last 5 years.
  3. Touching declining cells are joined into zones. Zones that lost < 0.05 km2 are dropped.

Writes
  public/data/zones.geojson        decline-zone outlines + their yearly area (shown on the map)
  stats.json > decline_zones            the same numbers for the Insights page / NGO alerts
  data_raw/gmw_v4/gmw4_lossyear_rgba.tif  every lost pixel coloured by the year it was lost (map layer)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box as sbox, mapping
from shapely.ops import unary_union

BBOX = [67.155304, 24.671376, 67.433395, 24.828817]  # Karachi mangrove coast study area, team box 2026-11-14
FIRST = 1985
CELL_M = 250
OUT = Path("data_raw/gmw_v4")
ZONES = Path("public/data/zones.geojson")
STATS = Path("public/data/stats.json")

MIN_PEAK_FRAC = 0.15     # cell must have been >= 15 % mangrove at its peak
MIN_LOSS_FRAC = 0.40     # lost >= 40 % of its peak
MAX_PEAK_YEAR = 2018     # decline has to have been going on for a while
MAX_TAU = -0.5           # mostly downhill after the peak
MIN_ZONE_LOSS_KM2 = 0.1


def kendall_tau(y):
    """Kendall tau of y against time (no scipy needed)."""
    n = len(y)
    if n < 4:
        return 0.0
    d = np.sign(y[None, :] - y[:, None])[np.triu_indices(n, 1)]
    return float(d.sum() / len(d))


def components(mask):
    """8-connected labelling of a small boolean grid."""
    lab = np.zeros(mask.shape, int)
    n = 0
    for i, j in zip(*np.nonzero(mask)):
        if lab[i, j]:
            continue
        n += 1
        stack = [(i, j)]
        lab[i, j] = n
        while stack:
            a, b = stack.pop()
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    x, y = a + da, b + db
                    if 0 <= x < mask.shape[0] and 0 <= y < mask.shape[1] and mask[x, y] and not lab[x, y]:
                        lab[x, y] = n
                        stack.append((x, y))
    return lab, n


def loss_year_colour(year):
    """Older losses pale yellow, recent losses deep red."""
    t = np.clip((year - 1986) / (2025 - 1986), 0, 1)[..., None]
    old, new = np.array([255, 230, 120]), np.array([200, 0, 40])
    return (old * (1 - t) + new * t).astype("uint8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tif")
    args = ap.parse_args()

    with rasterio.open(args.tif) as src:
        win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
        st = src.read(window=win) == 1          # (41, h, w)
        tr = src.window_transform(win)
        crs = src.crs
    years = np.arange(FIRST, FIRST + st.shape[0])
    lat0 = (BBOX[1] + BBOX[3]) / 2
    px_w = abs(tr.a) * 111320 * np.cos(np.radians(lat0))
    px_km2 = px_w * abs(tr.e) * 110574 / 1e6

    # ---- 1. pixel layer: year each pixel was lost (mangrove >= 3 years, gone in 2025) ----
    ever = st.sum(0)
    lost = (ever >= 3) & ~st[-1]
    last_year = FIRST + (st.shape[0] - 1 - np.argmax(st[::-1], axis=0))
    loss_year = np.where(lost, last_year + 1, 0)
    rgba = np.zeros(st.shape[1:] + (4,), "uint8")
    rgba[lost, :3] = loss_year_colour(loss_year[lost])
    rgba[lost, 3] = 255
    prof = dict(driver="GTiff", height=rgba.shape[0], width=rgba.shape[1], count=4, dtype="uint8",
                crs=crs, transform=tr, compress="deflate")
    with rasterio.open(OUT / "gmw4_lossyear_rgba.tif", "w", **prof) as d:
        d.write(rgba.transpose(2, 0, 1))
    print("wrote", OUT / "gmw4_lossyear_rgba.tif", "lost km2:", round(lost.sum() * px_km2, 2))

    # ---- 2. cells ----
    c = max(1, int(round(CELL_M / px_w)))
    H, W = st.shape[1] // c, st.shape[2] // c
    area = st[:, :H * c, :W * c].reshape(len(years), H, c, W, c).sum((2, 4)) * px_km2   # km2 per cell per year
    cell_km2 = c * c * px_km2
    peak = area.max(0)
    peak_i = area.argmax(0)
    last = area[-1]
    declining = np.zeros((H, W), bool)
    for i, j in zip(*np.nonzero(peak >= MIN_PEAK_FRAC * cell_km2)):
        pi = peak_i[i, j]
        if years[pi] > MAX_PEAK_YEAR or (peak[i, j] - last[i, j]) < MIN_LOSS_FRAC * peak[i, j]:
            continue
        after = area[pi:, i, j]
        if kendall_tau(after) > MAX_TAU:
            continue
        if after[-1] > 1.15 * after.min() + 1e-6 and after[-1] > area[-6, i, j]:
            continue  # recovering in the last 5 years
        declining[i, j] = True
    lab, n = components(declining)
    print(f"cells {H}x{W} ({c} px = {c * px_w:.0f} m), declining cells: {declining.sum()}, groups: {n}")

    # ---- 3. zones ----
    zones = []
    for k in range(1, n + 1):
        m = lab == k
        series = area[:, m].sum(1)
        pk = int(series.argmax())
        lost_km2 = float(series[pk] - series[-1])
        if lost_km2 < MIN_ZONE_LOSS_KM2:
            continue
        cells = [sbox(tr.c + j * c * tr.a, tr.f + (i + 1) * c * tr.e, tr.c + (j + 1) * c * tr.a, tr.f + i * c * tr.e)
                 for i, j in zip(*np.nonzero(m))]
        geom = unary_union(cells)
        zones.append({"geom": geom, "series": series, "peak_i": pk, "lost_km2": lost_km2, "cells": int(m.sum())})
    zones.sort(key=lambda z: -z["lost_km2"])

    features, summary = [], []
    for idx, z in enumerate(zones):
        zid = chr(ord("A") + idx) if idx < 26 else f"Z{idx}"
        s = z["series"]
        pk = z["peak_i"]
        k = years >= years[pk]
        slope = float(np.polyfit(years[k], s[k], 1)[0]) if k.sum() >= 3 else 0.0
        cen = z["geom"].centroid
        props = {
            "id": zid,
            "name": f"Decline zone {zid}",
            "centroid": [round(cen.x, 5), round(cen.y, 5)],
            "peak_year": int(years[pk]),
            "peak_km2": round(float(s[pk]), 3),
            "km2_2025": round(float(s[-1]), 3),
            "lost_km2": round(z["lost_km2"], 3),
            "lost_pct": round(100 * z["lost_km2"] / float(s[pk]), 1),
            "trend_km2_per_year": round(slope, 4),
            "cells": z["cells"],
            "years": [int(y) for y in years],
            "km2": [round(float(v), 4) for v in s],
        }
        features.append({"type": "Feature", "properties": props, "geometry": mapping(z["geom"].simplify(0))})
        summary.append({kk: props[kk] for kk in props if kk not in ("years", "km2")})
        print(zid, props["centroid"], f"peak {props['peak_year']} {props['peak_km2']} -> {props['km2_2025']} km2 "
              f"(-{props['lost_pct']}%), cells {props['cells']}")

    ZONES.write_text(json.dumps({"type": "FeatureCollection", "features": features}) + "\n", encoding="utf-8")
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    stats["decline_zones"] = {
        "source": "Global Mangrove Watch v4.1.12 annual extent 1985-2025 (Zenodo 21346457); zones found by CoastLens",
        "method": f"~{c * px_w:.0f} m cells; a cell is 'steadily declining' if after its peak year (<= {MAX_PEAK_YEAR}) "
                  f"it lost >= {int(MIN_LOSS_FRAC * 100)}% of its peak mangrove, its yearly area mostly falls "
                  f"(Kendall tau <= {MAX_TAU}) and it has not recovered in the last 5 years. Touching cells are "
                  f"joined into zones; zones that lost < {MIN_ZONE_LOSS_KM2} km2 are dropped.",
        "unit": "km2",
        "box_lost_pixels_km2": round(float(lost.sum() * px_km2), 2),
        "zones": summary,
    }
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", ZONES, "and stats.json > decline_zones;", len(features), "zones")


if __name__ == "__main__":
    main()
