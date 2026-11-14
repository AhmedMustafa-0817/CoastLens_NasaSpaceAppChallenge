"""NISAR statistics for the Insights page + an HV change layer.

- Mean backscatter (dB, averaged in linear power) inside the GMW 2020 mangrove
  extent and over open water, for each NISAR *_db.tif given.
- Optional HV change map (later minus earlier, dB) as an RGBA GeoTIFF for tiling.
  Only valid when both scenes come from the same track/frame/direction
  (identical geocoded grid). The script refuses otherwise.

    python scripts/nisar/nisar_stats_and_change.py \
        --scene 2025-11-20 HV data_raw/nisar/nisar_hv_20251120_db.tif \
        --scene 2026-10-10 HV data_raw/nisar/nisar_hv_20261010_db.tif \
        --scene 2026-10-10 HH data_raw/nisar/nisar_hh_20261010_db.tif \
        --mangrove data_raw/ee/gmw_2020.tif --water data_raw/ee/water_s2_2025_26.tif \
        --change data_raw/nisar/nisar_hv_20251120_db.tif data_raw/nisar/nisar_hv_20261010_db.tif \
        --change-out data_raw/nisar/nisar_hv_change_20251120_20261010
"""

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import xy
from rasterio.warp import transform

ROOT = Path(__file__).resolve().parents[2]
STATS = ROOT / "public" / "data" / "stats.json"


def sample_points(path, cond, n=50000, seed=0):
    with rasterio.open(path) as s:
        a = s.read()
        r, c = np.nonzero(cond(a))
        idx = np.random.default_rng(seed).choice(len(r), min(n, len(r)), replace=False)
        xs, ys = xy(s.transform, r[idx], c[idx])
        return s.crs, np.asarray(xs), np.asarray(ys)


def mean_db(db_path, pts):
    crs, xs, ys = pts
    with rasterio.open(db_path) as d:
        X, Y = transform(crs, d.crs, xs, ys)
        v = np.array([s[0] for s in d.sample(zip(X, Y))], dtype="float64")
    v = v[np.isfinite(v)]
    return float(10 * np.log10(np.mean(10 ** (v / 10)))), int(v.size)


def change_map(early, late, out, lim=6.0):
    with rasterio.open(early) as a, rasterio.open(late) as b:
        if a.crs != b.crs or a.transform != b.transform or a.shape != b.shape:
            raise SystemExit("Scenes are not on the same grid (different track/frame?). Refusing to difference.")
        d = b.read(1) - a.read(1)
        profile = a.profile
    valid = np.isfinite(d)
    t = np.clip(np.nan_to_num(d) / lim, -1, 1)  # -1 red (decrease) … 0 white … +1 blue (increase)
    r = np.where(t < 0, 255, 255 * (1 - t))
    g = 255 * (1 - np.abs(t))
    bl = np.where(t > 0, 255, 255 * (1 + t))
    rgba = np.stack([r, g, bl, np.where(valid, 255, 0)]).astype("uint8")
    profile.update(count=4, dtype="uint8", nodata=None)
    with rasterio.open(f"{out}_rgba.tif", "w", **profile) as dst:
        dst.write(rgba)
    profile.update(count=1, dtype="float32", nodata=np.nan)
    with rasterio.open(f"{out}_db.tif", "w", **profile) as dst:
        dst.write(d.astype("float32"), 1)
    print(f"Change map: median {np.nanmedian(d):+.2f} dB; wrote {out}_rgba.tif")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", nargs=3, action="append", metavar=("DATE", "POL", "DB_TIF"), required=True)
    ap.add_argument("--mangrove", required=True, help="GMW extent RGBA tif (alpha>0 = mangrove)")
    ap.add_argument("--water", required=True, help="water-mask RGBA tif, e.g. data_raw/ee/water_s2_2025_26.tif (alpha>0 = open water)")
    ap.add_argument("--change", nargs=2, metavar=("EARLY_DB", "LATE_DB"))
    ap.add_argument("--change-out")
    ap.add_argument("--source", default="NISAR L2 GCOV (provisional), track 142 ascending, frame 14; "
                                        "gamma0 with RTC, 2x2 multilooked to 20 m; mean of linear power inside GMW 2020 mangroves")
    args = ap.parse_args()

    mang = sample_points(args.mangrove, lambda a: a[3] > 0)
    water = sample_points(args.water, lambda a: a[3] > 0)
    series = []
    for date, pol, path in args.scene:
        m, n = mean_db(path, mang)
        w, _ = mean_db(path, water)
        series.append({"date": f"{date} {pol}", "pol": pol, "mean_db": round(m, 2), "water_db": round(w, 2), "n": n})
        print(f"{date} {pol}: mangrove {m:.2f} dB, open water {w:.2f} dB (n={n})")

    stats = json.loads(STATS.read_text(encoding="utf-8"))
    stats["nisar"] = {"source": args.source, "series": series}
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {STATS.relative_to(ROOT)}")

    if args.change:
        change_map(*args.change, args.change_out)


if __name__ == "__main__":
    main()
