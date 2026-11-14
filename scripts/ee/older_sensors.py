"""What the *older* satellites see, for the "old sensors vs NISAR" comparison.

    python scripts/ee/older_sensors.py            # both parts
    python scripts/ee/older_sensors.py --grid     # only part 1
    python scripts/ee/older_sensors.py --history  # only part 2

1. Raw values on the NISAR 20 m grid (data_raw/nisar/stack_164/grid.json), so every sensor is compared
   pixel-for-pixel with NISAR:  data_raw/ee/older_on_nisar_grid.tif, float32 bands
       1 Landsat 8/9 NDVI, dry season 2025-26 (optical, 30 m)
       2 Sentinel-1 VH dB, dry season 2025-26 (C-band radar, ~20 m)
       3 ALOS-2 PALSAR-2 HV dB, 2024 yearly mosaic (L-band radar, 25 m; the last L-band before NISAR)
       4 ALOS-2 PALSAR-2 HV dB, 2015 (for the 2015 -> 2024 long-term L-band change used by the alerts)
       5 Sentinel-1 VH dB, dry season 2017-18 (long-term C-band change)
2. Yearly history inside every decline zone (public/data/zones.geojson) and inside a reference of
   stable forest (mangrove in every GMW v4.1 year 2000-2025 is not available in EE, so we use "GMW v3
   mangrove in both 1996 and 2020"):
       Landsat 5/7/8/9 NDVI (dry season Nov-Feb, 1988-2025), ALOS/ALOS-2 HV (2007-2010, 2015-2024),
       Sentinel-1 VH (2015-2025).
   -> stats.json > zone_history
"""
import argparse
import json
import sys
import time
from pathlib import Path

import ee
import numpy as np
import rasterio
from affine import Affine
from rasterio.enums import Resampling
from rasterio.warp import reproject
import requests

sys.path.insert(0, str(Path(__file__).parent))
from export_layers import BBOX, GMW, ROOT, STATS_PATH, aoi, mangrove  # noqa: E402

GRID = ROOT / "data_raw" / "nisar" / "stack_164" / "grid.json"
OUT = ROOT / "data_raw" / "ee" / "older_on_nisar_grid.tif"
ZONES = ROOT / "public" / "data" / "zones.geojson"


def landsat_sr(year_start):
    """Dry-season (Nov year_start .. Feb year_start+1) Landsat 5/7/8/9 surface reflectance, harmonised."""
    a, b = f"{year_start}-11-01", f"{year_start + 1}-03-01"

    def prep(img, red, nir):
        qa = img.select("QA_PIXEL")
        clear = qa.bitwiseAnd(1 << 1).eq(0).And(qa.bitwiseAnd(1 << 3).eq(0)).And(qa.bitwiseAnd(1 << 4).eq(0))
        return img.updateMask(clear).select([red, nir], ["red", "nir"]).multiply(0.0000275).add(-0.2)

    cols = []
    for cid, red, nir in [("LANDSAT/LT05/C02/T1_L2", "SR_B3", "SR_B4"), ("LANDSAT/LE07/C02/T1_L2", "SR_B3", "SR_B4"),
                          ("LANDSAT/LC08/C02/T1_L2", "SR_B4", "SR_B5"), ("LANDSAT/LC09/C02/T1_L2", "SR_B4", "SR_B5")]:
        cols.append(ee.ImageCollection(cid).filterBounds(aoi()).filterDate(a, b)
                    .map(lambda i, red=red, nir=nir: prep(i, red, nir)))
    col = cols[0].merge(cols[1]).merge(cols[2]).merge(cols[3])
    return col.median().normalizedDifference(["nir", "red"]).rename("ndvi"), col.size()


def s1_vh(year_start):
    a, b = f"{year_start}-11-01", f"{year_start + 1}-03-01"
    col = (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi()).filterDate(a, b)
           .filter(ee.Filter.eq("instrumentMode", "IW")).filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
           .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")).select("VH"))
    return col.median().rename("s1_vh"), col.size()


def alos_hv(year):
    cid = "JAXA/ALOS/PALSAR/YEARLY/SAR" if year <= 2010 else "JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH"
    col = ee.ImageCollection(cid).filterBounds(aoi()).filter(ee.Filter.calendarRange(year, year, "year"))
    dn = ee.Image(col.first()).select("HV").toFloat()
    return dn.pow(2).log10().multiply(10).subtract(83).updateMask(dn.gt(0)).rename("alos_hv"), col.size()


def get(value, label, tries=5):
    for attempt in range(tries):
        try:
            return value.getInfo()
        except ee.EEException as e:
            if attempt == tries - 1:
                print(f"    {label}: FAILED {e}")
                return None
            time.sleep(8 * (attempt + 1))


def part_grid():
    g = json.loads(GRID.read_text())
    a, _, x0, _, e, y0 = g["transform"]
    h, w = g["shape"]
    bands = [("ndvi_2025_26", landsat_sr(2025)[0]), ("s1_vh_2025_26", s1_vh(2025)[0]), ("alos_hv_2024", alos_hv(2024)[0]),
             ("alos_hv_2015", alos_hv(2015)[0]), ("s1_vh_2017_18", s1_vh(2017)[0])]
    arrays = []
    for name, img in bands:
        pad = 0.003  # ~300 m margin so the snap onto the NISAR grid has no empty edges
        region = ee.Geometry.Rectangle([BBOX[0] - pad, BBOX[1] - pad, BBOX[2] + pad, BBOX[3] + pad])
        # ALOS: unmask() makes EE return all zeros for this mosaic, so its masked pixels come back as 0 instead
        img = img.toFloat() if name.startswith("alos") else img.toFloat().unmask(-9999)
        url = img.getDownloadURL({
            "crs": f"EPSG:{g['epsg']}", "scale": a, "region": region,
            "format": "GEO_TIFF"})
        tmp = OUT.with_suffix(f".{name}.tif")
        tmp.write_bytes(requests.get(url, timeout=600).content)
        dst_tr = Affine(a, 0, x0, 0, e, y0)
        arr = np.full((h, w), np.nan, "float32")
        with rasterio.open(tmp) as s:   # snap exactly onto the NISAR grid
            src = s.read(1).astype("float32")
            src[src <= -9998] = np.nan
            if name.startswith("alos"):
                src[src == 0] = np.nan
            reproject(src, arr, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan, dst_transform=dst_tr,
                      dst_crs=s.crs, dst_nodata=np.nan, resampling=Resampling.nearest)
        prof = dict(driver="GTiff", height=h, width=w, crs=f"EPSG:{g['epsg']}", transform=dst_tr)
        tmp.unlink()
        arrays.append(arr)
        print(f"  {name}: {np.isfinite(arr).mean() * 100:.0f}% valid, median {np.nanmedian(arr):.2f}")
    prof.update(count=len(arrays), dtype="float32", nodata=np.nan, compress="deflate")
    with rasterio.open(OUT, "w", **prof) as d:
        for i, arr in enumerate(arrays, 1):
            d.write(arr, i)
            d.set_band_description(i, bands[i - 1][0])
    print("wrote", OUT.relative_to(ROOT))


def part_history():
    zones = json.loads(ZONES.read_text(encoding="utf-8"))["features"]
    fc = ee.FeatureCollection([ee.Feature(ee.Geometry(f["geometry"]), {"id": f["properties"]["id"]}) for f in zones])
    ref = mangrove(1996).eq(1).And(mangrove(2020).eq(1))
    ref_geom = aoi()

    def zone_means(img, scale):
        """Mean of img inside every zone + inside stable reference forest."""
        z = img.reduceRegions(fc, ee.Reducer.mean(), scale).aggregate_array("mean")
        r = img.updateMask(ref).reduceRegion(ee.Reducer.mean(), ref_geom, scale, maxPixels=1e10).values().get(0)
        return ee.List(z).add(r)

    ids = [f["properties"]["id"] for f in zones] + ["reference"]
    series = {"ndvi": [], "alos_hv": [], "s1_vh": []}
    jobs = [("ndvi", y, *landsat_sr(y), 30) for y in range(1988, 2026)]
    jobs += [("alos_hv", y, *alos_hv(y), 25) for y in [2007, 2008, 2009, 2010] + list(range(2015, 2025))]
    jobs += [("s1_vh", y, *s1_vh(y), 20) for y in range(2015, 2026)]
    for key, year, img, count, scale in jobs:
        n = get(count, f"{key} {year} count")
        if not n:
            print(f"  {key} {year}: no scenes")
            continue
        vals = get(zone_means(img, scale), f"{key} {year}")
        if vals is None:
            continue
        series[key].append({"year": year + (1 if key != "alos_hv" else 0), "scenes": n,
                            **{i: (None if v is None else round(float(v), 3)) for i, v in zip(ids, vals)}})
        print(f"  {key} {year}: " + ", ".join(f"{i}={v:.2f}" for i, v in zip(ids, vals) if v is not None))
    stats = json.loads(STATS_PATH.read_text(encoding="utf-8"))
    stats["zone_history"] = {
        "note": "Mean value inside each GMW decline zone and inside stable reference forest (GMW v3 mangrove in "
                "both 1996 and 2020). 'year' = the year the dry season ends (Nov-Feb). NDVI: Landsat 5/7/8/9; "
                "ALOS HV: JAXA PALSAR/PALSAR-2 yearly mosaics (dB); S1 VH: Sentinel-1 GRD descending (dB).",
        "ids": ids,
        **series,
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote stats.json > zone_history")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="coastlens-momos")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--history", action="store_true")
    args = ap.parse_args()
    ee.Initialize(project=args.project)
    both = not (args.grid or args.history)
    if args.grid or both:
        part_grid()
    if args.history or both:
        part_history()


if __name__ == "__main__":
    main()
