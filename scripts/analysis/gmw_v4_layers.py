"""Map layers from the Global Mangrove Watch v4.1 annual stack (tile N25E067), clipped to the study box.

    python scripts/analysis/gmw_v4_layers.py data_raw/gmw_v4/gmw_mng_ext_v4112_stack/GMW_N25E067_v4112_mng_ext.tif

Writes data_raw/gmw_v4/<id>_rgba.tif for:
  gmw4_1985, gmw4_2025          mangrove extent (green)
  gmw4_change_1985_2025         red = mangrove in 1985 but not 2025, blue = new since 1985
Then tile them with scripts/tiles/make_tiles.py --categorical.
"""
import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

BBOX = [67.155304, 24.671376, 67.433395, 24.828817]  # Karachi mangrove coast study area (Rehri Goth to Port Qasim), team box 2026-11-14
MARGIN = 0.0
OUT = Path("data_raw/gmw_v4")
FIRST = 1985


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tif")
    args = ap.parse_args()
    l, b, r, t = BBOX
    with rasterio.open(args.tif) as src:
        win = from_bounds(l - MARGIN, b - MARGIN, r + MARGIN, t + MARGIN, transform=src.transform)
        win = win.round_offsets().round_lengths()
        tr = src.window_transform(win)
        band = lambda year: src.read(year - FIRST + 1, window=win) == 1
        y85, y25 = band(1985), band(2025)
        prof = dict(driver="GTiff", height=y85.shape[0], width=y85.shape[1], count=4, dtype="uint8",
                    crs=src.crs, transform=tr, compress="deflate")

    def save(id_, layers):
        rgba = np.zeros(y85.shape + (4,), "uint8")
        for mask, col in layers:
            rgba[mask] = (*col, 255)
        with rasterio.open(OUT / f"{id_}_rgba.tif", "w", **prof) as d:
            d.write(rgba.transpose(2, 0, 1))
        print("wrote", OUT / f"{id_}_rgba.tif")

    green, red, blue = (0, 170, 0), (230, 57, 70), (29, 111, 224)
    save("gmw4_1985", [(y85, green)])
    save("gmw4_2025", [(y25, green)])
    save("gmw4_change_1985_2025", [(y85 & ~y25, red), (~y85 & y25, blue)])


if __name__ == "__main__":
    main()
