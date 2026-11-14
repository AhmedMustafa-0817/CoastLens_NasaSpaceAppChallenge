"""Predicted tide height at every NISAR pass (track 164) -> docs/tide_at_pass.csv.

NISAR passes at the same clock time every 12 days, so it samples the spring-neap cycle with a repeat of about
64 days: the water level under the mangroves differs a lot from pass to pass. nisar_pixel_products.py reads the
table, adds tide as a covariate to the trend and reports how strongly the radar follows the tide.

Uses NASA's free GOT4.10 global ocean tide model through pyTMD (not in requirements.txt; the model is ~20 MB):

    pip install pyTMD h5py netCDF4
    python scripts/nisar/tide_at_pass.py [model_dir]

A global model at one open-water point just outside the creek mouths. Inside the creeks the tide arrives later and
is distorted, so treat the heights as "which passes were at high or low water", not as a local gauge.
"""
import csv
import sys
from pathlib import Path
import numpy as np
import pyTMD.datasets, pyTMD.compute

root = Path(__file__).resolve().parents[2]
mdir = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "data_raw" / "tide_model"
mdir.mkdir(parents=True, exist_ok=True)
MODEL = "GOT4.10_nc"
if not any(mdir.rglob("*.nc*")):
    pyTMD.datasets.fetch_gsfc_got("GOT4.10", directory=mdir, format="netcdf", timeout=600)
print("model files:", len(list(mdir.rglob("*.nc*"))))

LON, LAT = 67.15, 24.65      # open water just outside the creek mouths (Phitti / Khuddi creeks)
rows = [r for r in csv.DictReader(open(root / "docs/nisar_scenes_rehri_goth.csv", encoding="utf-8"))
        if r["product"] == "GCOV" and r["track"] == "164"]
times = sorted({r["start_utc"] for r in rows})
t = np.array([np.datetime64(x) for x in times])
epoch = np.datetime64("2000-01-01T00:00:00")
sec = (t - epoch) / np.timedelta64(1, "s")

def tide(seconds):
    out = pyTMD.compute.tide_elevations(np.full(len(seconds), LON), np.full(len(seconds), LAT), np.asarray(seconds, float),
                                        directory=mdir, model=MODEL, crs=4326, epoch=(2000, 1, 1, 0, 0, 0),
                                        type="drift", standard="UTC", method="linear", extrapolate=True, cutoff=200)
    return np.ma.filled(np.ma.asarray(out, dtype=float), np.nan)

h = tide(sec)
# context: the full range over the year at 10-minute steps
year = np.arange(sec[0], sec[-1], 600.0)
hy = tide(year)
print(f"year range {np.nanmin(hy):+.2f} .. {np.nanmax(hy):+.2f} m, sd {np.nanstd(hy):.2f}")
with open(root / "docs/tide_at_pass.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "time_utc", "tide_m", "source"])
    for x, v in zip(times, h):
        w.writerow([x[:10], x[11:19], f"{v:.2f}",
                    f"GOT4.10 global ocean tide model (NASA GSFC) via pyTMD, at {LAT} N {LON} E, relative to mean sea level"])
        print(x, f"{v:+.2f}")
print("at passes: min %.2f max %.2f sd %.2f" % (np.nanmin(h), np.nanmax(h), np.nanstd(h)))
