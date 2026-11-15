"""Per-pixel NISAR stack for the study box: every GCOV date of one track on one common 20 m grid.

Each date is read remotely (AOI window only), averaged in linear power onto a fixed UTM 42N 20 m grid
(so the 10 m dual-pol and 20 m quad-pol modes line up), and cached in data_raw/nisar/stack_<track>/.
nisar_pixel_products.py turns the stack into map layers.

    python scripts/nisar/nisar_pixel_stack.py --track 164
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import h5py
import numpy as np
from affine import Affine
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.warp import reproject, transform_bounds

sys.path.insert(0, str(Path(__file__).parent))
from nisar_timeseries import BBOX, EPSG, MB, ROOT, read_window, scenes  # noqa: E402
from remote_h5 import open_remote  # noqa: E402

RES = 20.0


def target_grid():
    l, b, r, t = transform_bounds("EPSG:4326", f"EPSG:{EPSG}", *BBOX)
    l, b = np.floor(l / RES) * RES, np.floor(b / RES) * RES
    r, t = np.ceil(r / RES) * RES, np.ceil(t / RES) * RES
    w, h = int(round((r - l) / RES)), int(round((t - b) / RES))
    return Affine(RES, 0, l, 0, -RES, t), (h, w)


def to_grid(values, transform, dst_tr, shape):
    src = np.where(np.isfinite(values) & (values > 0), values, np.nan).astype("float32")
    dst = np.full(shape, np.nan, "float32")
    reproject(src, dst, src_transform=transform, src_crs=CRS.from_epsg(EPSG), src_nodata=np.nan,
              dst_transform=dst_tr, dst_crs=CRS.from_epsg(EPSG), dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", type=int, default=164)
    args = ap.parse_args()
    warnings.simplefilter("ignore", RuntimeWarning)

    out = ROOT / "data_raw" / "nisar" / f"stack_{args.track}"
    out.mkdir(parents=True, exist_ok=True)
    dst_tr, shape = target_grid()
    (out / "grid.json").write_text(json.dumps({"epsg": EPSG, "transform": list(dst_tr)[:6], "shape": shape}))

    for (date,), url in scenes("GCOV", args.track):
        f_out = out / f"{date}.npz"
        if f_out.exists():
            continue
        try:
            f, _ = open_remote(url, block=MB)
            with h5py.File(f, "r") as h:
                g = h["science/LSAR/GCOV/grids/frequencyA"]
                layers = {}
                for pol in ("HVHV", "HHHH"):
                    vals, tr = read_window(g, pol)
                    layers[pol[:2].lower()] = to_grid(vals, tr, dst_tr, shape)
                mode = url.split("_D_076_")[-1][:9] if "_D_076_" in url else ""
        except (RuntimeError, OSError) as e:
            print(f"SKIPPED {date}: {str(e)[:120]}", flush=True)
            continue
        np.savez_compressed(f_out, mode=mode, url=url, **layers)
        print(f"{date} {mode} ok ({f.bytes_fetched / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
