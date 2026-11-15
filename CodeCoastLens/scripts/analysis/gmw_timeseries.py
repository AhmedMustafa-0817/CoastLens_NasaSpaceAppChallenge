"""Yearly mangrove area (1985-2025) inside the study box from Global Mangrove Watch v4.1.

Input: the GMW v4.1.12 41-band stack tile that covers the box (band 1 = 1985 ... band 41 = 2025),
from https://zenodo.org/records/21346457 (gmw_mng_ext_v4112_stack.tar.gz, tile N25E067).

    python scripts/analysis/gmw_timeseries.py data_raw/gmw_v4/<...N25E067...>.tif

Writes stats.json > gmw_timeseries and data_raw/gmw_v4/box_gmw_v4_area.csv. "km2" is the plain mapped
area (matches the GMW website's custom-area numbers within ~1 %); "km2_corrected" applies GMW's global
accuracy factor 0.9775 used in their country statistics.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

BBOX = [67.155304, 24.671376, 67.433395, 24.828817]  # Karachi mangrove coast study area (Rehri Goth to Port Qasim), team box 2026-11-14
STATS = Path("public/data/stats.json")
CORRECTION = 0.9775
FIRST_YEAR = 1985


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tif")
    ap.add_argument("--stats", default=str(STATS))
    args = ap.parse_args()

    with rasterio.open(args.tif) as src:
        assert src.crs.to_epsg() == 4326, src.crs
        win = from_bounds(*BBOX, transform=src.transform).round_offsets().round_lengths()
        data = src.read(window=win)
        t = src.window_transform(win)
        nodata = src.nodata
    # area of one pixel (deg -> m) at each row's latitude
    rows = np.arange(data.shape[1])
    lat = t.f + (rows + 0.5) * t.e
    px_m2 = (abs(t.a) * 111320 * np.cos(np.radians(lat))) * (abs(t.e) * 110574)

    years = []
    for b in range(data.shape[0]):
        band = data[b]
        mang = band == 1 if nodata is None else (band == 1) & (band != nodata)
        km2 = float((mang * px_m2[:, None]).sum() / 1e6)
        years.append({"year": FIRST_YEAR + b, "km2": round(km2, 2), "km2_corrected": round(km2 * CORRECTION, 2)})

    first, last = years[0], years[-1]
    peak = max(years, key=lambda y: y["km2"])
    low = min(years, key=lambda y: y["km2"])
    out = {
        "source": "Global Mangrove Watch v4.1.12 (Aberystwyth University / JAXA, July 2026), "
                  "annual extent from Landsat, Sentinel-2 and JAXA L-band; area computed by CoastLens within the AOI",
        "url": "https://zenodo.org/records/21346457",
        "unit": "km2",
        "pixel_deg": abs(t.a),
        "correction_factor": CORRECTION,
        "note": "km2 is the plain mapped area (matches the GMW website's custom-area widget within ~1%); "
                "km2_corrected applies GMW's global accuracy correction (x0.9775) used in their country totals. "
                "GMW reports ~93% accuracy globally; local accuracy varies.",
        "years": years,
        "summary": {
            "first": first, "last": last, "peak": peak, "lowest": low,
            "net_change_km2": round(last["km2"] - first["km2"], 2),
            "net_change_pct": round(100 * (last["km2"] - first["km2"]) / first["km2"], 1),
        },
    }
    stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    stats["gmw_timeseries"] = out
    Path(args.stats).write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for y in years:
        print(y["year"], y["km2"], y["km2_corrected"])
    csv_path = Path("data_raw/gmw_v4/box_gmw_v4_area.csv")
    lines = ["year,km2,km2_corrected"] + [f'{y["year"]},{y["km2"]},{y["km2_corrected"]}' for y in years]
    csv_path.write_text("\n".join(lines) + "\n")
    print("summary", out["summary"])


if __name__ == "__main__":
    main()
