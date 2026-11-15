"""Convert one polarisation of a NISAR L2 GCOV product (HDF5) into GeoTIFFs.

Writes two files:
  <out>_db.tif   float32 backscatter in dB (for analysis / statistics)
  <out>_rgba.tif uint8 greyscale + alpha (for scripts/tiles/make_tiles.py)

FIRST run --inspect on a real downloaded file. The default dataset paths below
follow our reading of the NISAR GCOV product layout and MUST be checked
against the actual file and the official product specification before use.

    python scripts/nisar/nisar_gcov_to_geotiff.py NISAR_L2_GCOV_....h5 --inspect
    python scripts/nisar/nisar_gcov_to_geotiff.py NISAR_L2_GCOV_....h5 --pol HVHV \
        --bbox 67.155304 24.671376 67.433395 24.828817 --out nisar_hv_20260801
"""

import argparse
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds as window_from_bounds

DEFAULT_GRID = "/science/LSAR/GCOV/grids/frequencyA"  # verify with --inspect


def inspect(path):
    def show(name, obj):
        if isinstance(obj, h5py.Dataset):
            print(f"{name}  shape={obj.shape} dtype={obj.dtype}")
            for k, v in obj.attrs.items():
                if k.lower() in ("epsg_code", "units", "description", "spatial_ref", "_fillvalue"):
                    print(f"    @{k} = {v!r}"[:200])
    with h5py.File(path, "r") as f:
        f.visititems(show)


def read_epsg(grid, args):
    if args.epsg:
        return args.epsg
    proj = grid.get("projection")
    if proj is not None:
        for key in ("epsg_code", "epsg"):
            if key in proj.attrs:
                return int(np.asarray(proj.attrs[key]).ravel()[0])
        try:
            return int(np.asarray(proj[()]).ravel()[0])
        except (TypeError, ValueError):
            pass
    sys.exit("Could not find the EPSG code. Run --inspect and pass --epsg.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("h5", help="local .h5 path, or an https:// NISAR URL (read remotely, AOI only)")
    ap.add_argument("--looks", type=int, default=1,
                    help="average NxN pixels in linear power before dB (reduces speckle; 2 = 20 m from 10 m)")
    ap.add_argument("--inspect", action="store_true", help="list every dataset in the file and exit")
    ap.add_argument("--grid", default=DEFAULT_GRID, help=f"HDF5 group holding the rasters (default {DEFAULT_GRID})")
    ap.add_argument("--pol", default="HVHV", help="covariance term, e.g. HHHH or HVHV")
    ap.add_argument("--epsg", type=int, help="override the projection EPSG code")
    ap.add_argument("--bbox", type=float, nargs=4, metavar=("W", "S", "E", "N"), help="clip to lon/lat box")
    ap.add_argument("--vmin", type=float, default=-25.0, help="dB shown as black (default -25)")
    ap.add_argument("--vmax", type=float, default=-5.0, help="dB shown as white (default -5)")
    ap.add_argument("--out", required=False, help="output prefix, e.g. nisar_hv_20260801")
    ap.add_argument("--linear", action="store_true",
                    help="values are not power (e.g. GUNW coherence 0-1): no dB conversion; "
                         "use with --vmin 0 --vmax 1 and --pol HH/coherenceMagnitude")
    args = ap.parse_args()

    source = args.h5
    if args.h5.startswith("http"):
        from remote_h5 import open_remote
        source, _ = open_remote(args.h5)

    if args.inspect:
        inspect(source)
        return
    if not args.out:
        sys.exit("--out is required unless --inspect is used")

    with h5py.File(source, "r") as f:
        if args.grid not in f:
            sys.exit(f"Group {args.grid} not found. Run --inspect to find the right path.")
        grid = f[args.grid]
        if args.pol not in grid:
            sys.exit(f"{args.pol} not in {args.grid}. Available: {sorted(k for k in grid if isinstance(grid[k], h5py.Dataset))}")
        x = grid["xCoordinates"][()]
        y = grid["yCoordinates"][()]
        dx, dy = float(x[1] - x[0]), float(y[1] - y[0])
        # Coordinates are pixel centres; the affine transform needs the outer corner.
        transform = Affine(dx, 0, float(x[0]) - dx / 2, 0, dy, float(y[0]) - dy / 2)
        crs = CRS.from_epsg(read_epsg(grid, args))

        rows, cols = slice(0, len(y)), slice(0, len(x))
        if args.bbox:
            l, b, r, t = transform_bounds("EPSG:4326", crs, *args.bbox)
            win = window_from_bounds(l, b, r, t, transform).round_offsets().round_lengths()
            r0, c0 = max(int(win.row_off), 0), max(int(win.col_off), 0)
            r1, c1 = min(r0 + int(win.height), len(y)), min(c0 + int(win.width), len(x))
            if r1 <= r0 or c1 <= c0:
                sys.exit("The bbox does not overlap this scene.")
            rows, cols = slice(r0, r1), slice(c0, c1)
            transform = transform * Affine.translation(c0, r0)

        power = grid[args.pol][rows, cols].astype("float64")  # lazy slice: only the AOI is read

    if args.looks > 1:
        k = args.looks
        h, w = (power.shape[0] // k) * k, (power.shape[1] // k) * k
        blocks = power[:h, :w].reshape(h // k, k, w // k, k)
        blocks = np.where(blocks > 0, blocks, np.nan)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            power = np.nanmean(blocks, axis=(1, 3))
        transform = transform * Affine.scale(k, k)

    valid = np.isfinite(power) & (power > 0)
    db = np.full(power.shape, np.nan, dtype="float32")
    db[valid] = power[valid] if args.linear else 10.0 * np.log10(power[valid])
    suffix, unit = ("value", "") if args.linear else ("db", " dB")

    profile = dict(driver="GTiff", height=db.shape[0], width=db.shape[1], crs=crs,
                   transform=transform, compress="deflate", tiled=True)
    with rasterio.open(f"{args.out}_{suffix}.tif", "w", count=1, dtype="float32", nodata=np.nan, **profile) as dst:
        dst.write(db, 1)

    grey = np.zeros(db.shape, dtype="uint8")
    grey[valid] = np.clip((db[valid] - args.vmin) / (args.vmax - args.vmin) * 255, 0, 255).astype("uint8")
    alpha = np.where(valid, 255, 0).astype("uint8")
    with rasterio.open(f"{args.out}_rgba.tif", "w", count=4, dtype="uint8", **profile) as dst:
        dst.write(np.stack([grey, grey, grey, alpha]))

    print(f"{args.pol}: {valid.sum()} valid pixels, range {np.nanmin(db):.2f} to {np.nanmax(db):.2f}{unit}")
    print(f"Wrote {args.out}_{suffix}.tif and {args.out}_rgba.tif")
    print(f"Next: python scripts/tiles/make_tiles.py {args.out}_rgba.tif public/tiles/{Path(args.out).name}")


if __name__ == "__main__":
    main()
