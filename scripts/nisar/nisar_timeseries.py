"""Year-long NISAR time series over the study area: backscatter (GCOV) and coherence (GUNW).

Reads only the AOI window, so each scene costs a few MB instead of GBs.
  --freq A (default): full-resolution grids (GCOV frequencyA 10-20 m, GUNW wrappedInterferogram 20 m).
                      Right for a small AOI such as Rehri Goth (~4 x 3 km).
  --freq B:           coarse 80 m grids (GCOV frequencyB, GUNW unwrappedInterferogram). Faster for big AOIs.
For every scene it reports the mean inside three zones:
  mangrove   = Global Mangrove Watch 2020 extent (>50 % of the 80 m cell)
  water      = open water/creeks (Sentinel-2 2025-26 MNDWI > 0 in >90 % of the cell)
  other land = not water (<10 %) and not mangrove (<10 %)

Results go into public/data/stats.json under "nisar_timeseries".

    python scripts/nisar/nisar_timeseries.py --track 164            # Rehri Goth, full resolution
"""

import argparse
import csv
import json
import re
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds
from rasterio.windows import from_bounds as window_from_bounds

sys.path.insert(0, str(Path(__file__).parent))
from remote_h5 import open_remote  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CSV = ROOT / "docs" / "nisar_scenes_rehri_goth.csv"
STATS = ROOT / "public" / "data" / "stats.json"
GMW = ROOT / "data_raw" / "ee" / "gmw_2020.tif"
WATER = ROOT / "data_raw" / "ee" / "water_s2_2025_26.tif"  # Sentinel-2 MNDWI > 0
BBOX = (67.155304, 24.671376, 67.433395, 24.828817)  # Karachi mangrove coast study area (Rehri Goth to Port Qasim), team box 2026-11-14
EPSG = 32642
MB = 1024 * 1024
CACHE = ROOT / "data_raw" / "nisar" / "timeseries_cache.json"  # resume after network drops


def scenes(product, track):
    """One URL per acquisition (pair for GUNW). If several versions exist, prefer V1 > PROVISIONAL > BETA
    (early BETA GCOV files read ~3 dB darker than the PROVISIONAL reprocessing of the same date)."""
    rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8"))
            if r["product"] == product and r["track"] == str(track)]
    out = {}
    rank = lambda u: 0 if "_BETA_" in u else 1 if "_PROVISIONAL_" in u else 2
    for r in sorted(rows, key=lambda r: (rank(r["url"]), r["file"])):
        dates = re.findall(r"_(\d{8})T\d{6}", r["file"])
        key = (dates[0], dates[2]) if product == "GUNW" else (dates[0],)
        out[key] = r["url"]
    return sorted(out.items())


def read_window(grid, name):
    x, y = grid["xCoordinates"][()], grid["yCoordinates"][()]
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
    tr = Affine(dx, 0, float(x[0]) - dx / 2, 0, dy, float(y[0]) - dy / 2)
    l, b, r, t = transform_bounds("EPSG:4326", f"EPSG:{EPSG}", *BBOX)
    w = window_from_bounds(l, b, r, t, tr).round_offsets().round_lengths()
    r0, c0 = max(int(w.row_off), 0), max(int(w.col_off), 0)
    r1, c1 = min(r0 + int(w.height), len(y)), min(c0 + int(w.width), len(x))
    data = grid[name][r0:r1, c0:c1].astype("float64")
    return data, tr * Affine.translation(c0, r0)


def zone_masks(shape, transform, cache={}):
    key = (shape, tuple(transform))
    if key in cache:
        return cache[key]

    def frac(path, fn):
        with rasterio.open(path) as s:
            src = fn(s.read(4)).astype("float32")
            dst = np.zeros(shape, "float32")
            reproject(src, dst, src_transform=s.transform, src_crs=s.crs, dst_transform=transform,
                      dst_crs=CRS.from_epsg(EPSG), resampling=Resampling.average)
        return dst

    mang = frac(GMW, lambda a: a > 0)
    wat = frac(WATER, lambda a: a > 0)
    cache[key] = {"mangrove": mang > 0.5, "water": wat > 0.9, "land": (wat < 0.1) & (mang < 0.1)}
    return cache[key]


def zone_means(values, transform, as_db):
    out = {}
    for zone, m in zone_masks(values.shape, transform).items():
        v = values[m & np.isfinite(values) & (values > 0)]
        if v.size < 50:
            out[zone] = None
            continue
        mean = float(v.mean())
        out[zone] = round(10 * np.log10(mean), 2) if as_db else round(mean, 3)
    return out


def iso(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", type=int, default=164)
    ap.add_argument("--freq", choices=["A", "B"], default="A")
    args = ap.parse_args()
    warnings.simplefilter("ignore", RuntimeWarning)

    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    def save(key, row):
        cache[key] = row
        CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))

    backscatter, coherence = [], []
    for (date,), url in scenes("GCOV", args.track):
        if f"GCOV {date}" in cache:
            backscatter.append(cache[f"GCOV {date}"])
            continue
        f, _ = open_remote(url, block=MB)
        with h5py.File(f, "r") as h:
            g = h[f"science/LSAR/GCOV/grids/frequency{args.freq}"]
            row = {"date": iso(date)}
            for pol, key in (("HVHV", "hv"), ("HHHH", "hh")):
                vals, tr = read_window(g, pol)
                for zone, v in zone_means(vals, tr, as_db=True).items():
                    row[f"{zone}_{key}"] = v
        row = {k: (float(v) if isinstance(v, (float, np.floating)) else v) for k, v in row.items()}
        backscatter.append(row)
        save(f"GCOV {date}", row)
        print(f"GCOV {row}  ({f.bytes_fetched / 1e6:.1f} MB)", flush=True)

    for (d1, d2), url in scenes("GUNW", args.track):
        if f"GUNW {d1} {d2}" in cache:
            coherence.append(cache[f"GUNW {d1} {d2}"])
            continue
        try:
            f, _ = open_remote(url, block=MB)
            with h5py.File(f, "r") as h:
                g = h["science/LSAR/GUNW/grids/frequencyA/" + ("wrappedInterferogram" if args.freq == "A" else "unwrappedInterferogram")]
                vals, tr = read_window(g, "HH/coherenceMagnitude")
        except (RuntimeError, OSError) as e:
            print(f"SKIPPED GUNW {d1}-{d2}: {str(e)[:120]}", flush=True)
            continue
        days = int((np.datetime64(iso(d2)) - np.datetime64(iso(d1))) / np.timedelta64(1, "D"))
        row = {"pair": f"{iso(d1)} to {iso(d2)}", "mid": str(np.datetime64(iso(d1)) + days // 2), "days": days,
               **zone_means(vals, tr, as_db=False)}
        row = {k: (float(v) if isinstance(v, np.floating) else v) for k, v in row.items()}
        coherence.append(row)
        save(f"GUNW {d1} {d2}", row)
        print(f"GUNW {row}  ({f.bytes_fetched / 1e6:.1f} MB)", flush=True)

    # Quality control: a pair whose coherence is ~equal and very low in EVERY zone means one
    # acquisition is bad (a real landscape never decorrelates uniformly). Find the date shared by
    # such pairs, then hide those points from charts (raw values kept under "raw").
    bad_pairs = [c for c in coherence
                 if all(c.get(z) is not None for z in ("mangrove", "land", "water"))
                 and max(c["mangrove"], c["land"], c["water"]) < 0.3  # 20 m coherence has a ~0.24 noise floor
                 and max(c["mangrove"], c["land"], c["water"]) - min(c["mangrove"], c["land"], c["water"]) < 0.02]
    dates = [d for c in bad_pairs for d in c["pair"].split(" to ")]
    suspect = {d for d in dates if dates.count(d) >= 2} or set(dates)
    note = "suspect acquisition: uniform near-zero coherence in all zones (sensor/processing issue, not landscape change)"
    for c in coherence:
        if any(d in c["pair"] for d in suspect):
            c["raw"] = {z: c[z] for z in ("mangrove", "land", "water")}
            c.update(mangrove=None, land=None, water=None, qc=note)
    for b in backscatter:
        if b["date"] in suspect:
            b["raw"] = {k: v for k, v in b.items() if k.endswith(("_hv", "_hh"))}
            b.update({k: None for k in b["raw"]}, qc=note)
    if suspect:
        print(f"QC: suspect acquisition(s) {sorted(suspect)} hidden from charts")

    stats = json.loads(STATS.read_text(encoding="utf-8"))
    stats["nisar_timeseries"] = {
        "track": args.track,
        "backscatter": {
            "source": f"NISAR L2 GCOV, track {args.track}, frequency{args.freq} grid ({'10-20 m' if args.freq == 'A' else '80 m'}); zone mean of linear power, in dB",
            "series": backscatter,
        },
        "coherence": {
            "source": f"NISAR L2 GUNW, track {args.track}, HH coherence magnitude, {'20 m' if args.freq == 'A' else '80 m'} grid; zone mean",
            "series": coherence,
        },
        "zones": "mangrove = GMW 2020 (>50% of cell); water = Sentinel-2 MNDWI water (>90%); land = neither (<10% of each)",
        "qc_suspect_dates": sorted(suspect),
    }
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(backscatter)} backscatter dates and {len(coherence)} coherence pairs to {STATS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
