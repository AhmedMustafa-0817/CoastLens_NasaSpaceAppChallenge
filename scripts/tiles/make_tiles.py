"""Cut a colourised GeoTIFF into XYZ web-map tiles for the CoastLens site.

Input: an 8-bit RGB or RGBA GeoTIFF (what scripts/ee/export_layers.js and
scripts/nisar/nisar_gcov_to_geotiff.py produce). Band 4, if present, is alpha.
Output: <out_dir>/{z}/{x}/{y}.png, which Leaflet reads directly.

Pure Python (rasterio + mercantile + Pillow), so no GDAL command-line install
is needed on Windows.

    python scripts/tiles/make_tiles.py l8_truecolor_2024_25.tif public/tiles/l8_truecolor_2024_25
    python scripts/tiles/make_tiles.py gmw_2020.tif public/tiles/gmw_2020 --categorical
"""

import argparse
import sys
from pathlib import Path

import mercantile
import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

TILE = 256


def parse_zoom(text):
    lo, _, hi = text.partition("-")
    lo, hi = int(lo), int(hi or lo)
    if not 0 <= lo <= hi <= 20:
        raise argparse.ArgumentTypeError("zoom must look like 9-14")
    return lo, hi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="RGB/RGBA uint8 GeoTIFF")
    ap.add_argument("out_dir", type=Path, help="e.g. public/tiles/<layer-id>")
    ap.add_argument("--zoom", type=parse_zoom, default=(9, 14), help="zoom range, default 9-14")
    ap.add_argument("--categorical", action="store_true",
                    help="nearest-neighbour resampling (use for class maps such as mangrove extent)")
    ap.add_argument("--colors", type=int, default=0,
                    help="quantize colour tiles to N colours (e.g. 64) to shrink noisy layers like change maps")
    ap.add_argument("--clip", type=float, nargs=4, metavar=("W", "S", "E", "N"),
                    help="make everything outside this lon/lat box transparent (layers on a UTM grid stick out "
                         "slightly past the study box otherwise)")
    args = ap.parse_args()

    resampling = Resampling.nearest if args.categorical else Resampling.bilinear
    zmin, zmax = args.zoom

    with rasterio.open(args.input) as src:
        if src.count not in (3, 4) or src.dtypes[0] != "uint8":
            sys.exit(f"{args.input}: expected 3 or 4 uint8 bands, got {src.count} x {src.dtypes[0]}. "
                     "Export a colourised image (RGB + alpha), not raw values.")
        has_alpha = src.count == 4
        west, south, east, north = transform_bounds(src.crs, "EPSG:4326", *src.bounds)

        written = skipped = 0
        for tile in mercantile.tiles(west, south, east, north, range(zmin, zmax + 1)):
            b = mercantile.xy_bounds(tile)
            vrt_opts = dict(
                crs="EPSG:3857",
                transform=from_bounds(b.left, b.bottom, b.right, b.top, TILE, TILE),
                width=TILE,
                height=TILE,
                resampling=resampling,
            )
            # 3-band input: let GDAL build alpha from the footprint. 4-band: band 4 is alpha
            # and areas outside the source come back as 0 (= transparent).
            if not has_alpha:
                vrt_opts["add_alpha"] = True
            with WarpedVRT(src, **vrt_opts) as vrt:
                data = vrt.read()  # (4, 256, 256)

            if args.clip:
                W, S, E, N = args.clip
                xs = b.left + (np.arange(TILE) + 0.5) * (b.right - b.left) / TILE
                ys = b.top - (np.arange(TILE) + 0.5) * (b.top - b.bottom) / TILE
                lon = np.degrees(xs / 6378137.0)
                lat = np.degrees(2 * np.arctan(np.exp(ys / 6378137.0)) - np.pi / 2)
                inside = ((lat >= S) & (lat <= N))[:, None] & ((lon >= W) & (lon <= E))[None, :]
                data[3][~inside] = 0
            if not data[3].any():
                skipped += 1
                continue
            path = args.out_dir / str(tile.z) / str(tile.x) / f"{tile.y}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            if np.array_equal(data[0], data[1]) and np.array_equal(data[1], data[2]):
                # greyscale (e.g. radar): grey + alpha PNG is about half the size
                img = Image.fromarray(np.stack([data[0], data[3]], axis=-1), "LA")
            else:
                img = Image.fromarray(np.moveaxis(data[:4], 0, -1), "RGBA")
                if args.colors:
                    img = img.quantize(colors=args.colors, method=Image.Quantize.FASTOCTREE)
            img.save(path, optimize=True)
            written += 1

    print(f"{written} tiles written to {args.out_dir} (zoom {zmin}-{zmax}); {skipped} empty tiles skipped.")
    print("Now set this layer's status to \"ready\" in public/data/layers.json.")


if __name__ == "__main__":
    main()
