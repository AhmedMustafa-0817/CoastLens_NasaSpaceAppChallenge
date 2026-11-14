"""Export CoastLens map layers + statistics from Earth Engine straight to this PC.

Python twin of export_layers.js (same datasets, dates, masks and styles), but it
downloads directly instead of going through Google Drive.

    python scripts/ee/export_layers.py                    # all layers + stats
    python scripts/ee/export_layers.py --only gmw_2020    # selected layers
    python scripts/ee/export_layers.py --stats-only

Needs: `earthengine authenticate` done once, and an EE-registered Cloud project.
Writes GeoTIFFs to data_raw/ee/<id>.tif (RGB + alpha, uint8, EPSG:3857) and
public/data/stats.json.
"""

import argparse
import datetime as dt
import json
import math
import sys
import time
from pathlib import Path

import ee
import numpy as np
import rasterio
import requests
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data_raw" / "ee"
STATS_PATH = ROOT / "public" / "data" / "stats.json"

BBOX = [67.155304, 24.671376, 67.433395, 24.828817]  # Karachi mangrove coast study area (Rehri Goth to Port Qasim), team box 2026-11-14
SEASONS = {
    "2015_16": ("2015-11-01", "2016-03-01"),
    "2017_18": ("2017-11-01", "2018-03-01"),
    "2018_19": ("2018-11-01", "2019-03-01"),
    "2021_22": ("2021-11-01", "2022-03-01"),
    "2024_25": ("2024-11-01", "2025-03-01"),
    "2025_26": ("2025-11-01", "2026-03-01"),
}
STYLE = {
    "truecolor": {"bands": ["red", "green", "blue"], "min": 0, "max": 0.25},
    "ndvi": {"min": 0, "max": 0.8, "palette": ["8b4513", "ffff00", "008000"]},
    "ndviChange": {"min": -0.4, "max": 0.4, "palette": ["ff0000", "ffffff", "0000ff"]},
    "s1": {"min": -25, "max": -5, "palette": ["000000", "ffffff"]},
    "mangrove": {"min": 1, "max": 1, "palette": ["00aa00"]},
    "lossGain": {"min": 1, "max": 2, "palette": ["e63946", "1d6fe0"]},
    "water": {"min": 1, "max": 1, "palette": ["1d6fe0"]},
}
GMW = "projects/earthengine-legacy/assets/projects/sat-io/open-datasets/GMW/extent/"
MAX_CHUNK_BYTES = 24e6  # getDownloadURL limit is ~32 MB per request
COS_LAT = math.cos(math.radians((BBOX[1] + BBOX[3]) / 2))


# ---------- image builders (same logic as export_layers.js) ----------
def aoi():
    return ee.Geometry.Rectangle(BBOX)


def mask_landsat(img):
    qa = img.select("QA_PIXEL")
    clear = (qa.bitwiseAnd(1 << 1).eq(0)
             .And(qa.bitwiseAnd(1 << 3).eq(0))
             .And(qa.bitwiseAnd(1 << 4).eq(0)))
    return (img.updateMask(clear)
            .select(["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6"], ["blue", "green", "red", "nir", "swir1"])
            .multiply(0.0000275).add(-0.2))


def landsat8(season):
    a, b = SEASONS[season]
    col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(aoi()).filterDate(a, b)
    return col.map(mask_landsat).median().clip(aoi()), col.size()


def sentinel2(season):
    a, b = SEASONS[season]
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")
    col = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi()).filterDate(a, b)
    img = (col.linkCollection(cs, ["cs_cdf"])
           .map(lambda i: i.updateMask(i.select("cs_cdf").gte(0.6))
                .select(["B2", "B3", "B4", "B8", "B11"], ["blue", "green", "red", "nir", "swir1"])
                .divide(10000))
           .median().clip(aoi()))
    return img, col.size()


def s1_collection(season, orbit_pass):
    a, b = SEASONS[season]
    return (ee.ImageCollection("COPERNICUS/S1_GRD").filterBounds(aoi()).filterDate(a, b)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.eq("orbitProperties_pass", orbit_pass))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
            .select("VH"))


def sentinel1_vh(season, orbit_pass):
    col = s1_collection(season, orbit_pass)
    return col.map(lambda i: i.focalMedian(30, "circle", "meters")).median().clip(aoi()), col.size()


def alos_hv(year):
    """JAXA ALOS/ALOS-2 PALSAR yearly L-band mosaic (25 m), HV in dB: 10*log10(DN^2) - 83."""
    cid = "JAXA/ALOS/PALSAR/YEARLY/SAR" if year <= 2010 else "JAXA/ALOS/PALSAR/YEARLY/SAR_EPOCH"
    img = ee.ImageCollection(cid).filterBounds(aoi()).filter(ee.Filter.calendarRange(year, year, "year")).first()
    dn = img.select("HV").toFloat()
    return dn.pow(2).log10().multiply(10).subtract(83).updateMask(dn.gt(0)).clip(aoi()), None


def ndvi(img):
    return img.normalizedDifference(["nir", "red"]).rename("ndvi")


def water(season="2025_26"):
    """Open water/creeks: Sentinel-2 median MNDWI (green vs SWIR) > 0. Analysis mask, not shown on the site."""
    img, _ = sentinel2(season)
    return img.normalizedDifference(["green", "swir1"]).gt(0).rename("water")


def mangrove(year):
    vectors = ee.FeatureCollection(f"{GMW}gmw_v3_{year}_vec").filterBounds(aoi())
    return ee.Image(0).byte().paint(vectors, 1).clip(aoi()).rename("mangrove")


def rgba(img, vis):
    v = img.visualize(**vis)
    alpha = v.mask().reduce(ee.Reducer.min()).multiply(255).rename("alpha")
    return v.addBands(alpha).unmask(0).toUint8()


# ---------- download ----------
def download(image, out_path, ground_m):
    """Download an RGBA image over the AOI, splitting into chunks under the size limit."""
    scale = ground_m / COS_LAT  # EPSG:3857 metres are stretched by 1/cos(lat)
    w_m = (BBOX[2] - BBOX[0]) * 111320 * COS_LAT  # approx ground width (m)
    h_m = (BBOX[3] - BBOX[1]) * 110570
    est = (w_m / ground_m) * (h_m / ground_m) * 4
    n = max(1, math.ceil(math.sqrt(est / MAX_CHUNK_BYTES)))
    xs = np.linspace(BBOX[0], BBOX[2], n + 1)
    ys = np.linspace(BBOX[1], BBOX[3], n + 1)
    parts = []
    for i in range(n):
        for j in range(n):
            region = ee.Geometry.Rectangle([xs[i], ys[j], xs[i + 1], ys[j + 1]])
            url = image.getDownloadURL({"region": region, "scale": scale, "crs": "EPSG:3857", "format": "GEO_TIFF"})
            part = out_path.with_suffix(f".part{i}_{j}.tif")
            for attempt in range(4):
                try:
                    r = requests.get(url, timeout=600)
                    r.raise_for_status()
                    part.write_bytes(r.content)
                    break
                except requests.RequestException as e:
                    if attempt == 3:
                        raise
                    print(f"    retry {attempt + 1} ({e})")
                    time.sleep(5 * (attempt + 1))
            parts.append(part)
    if len(parts) == 1:
        parts[0].replace(out_path)
    else:
        srcs = [rasterio.open(p) for p in parts]
        mosaic, transform = merge(srcs)
        profile = srcs[0].profile | {"height": mosaic.shape[1], "width": mosaic.shape[2],
                                     "transform": transform, "compress": "deflate", "tiled": True}
        for s in srcs:
            s.close()
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(mosaic)
        for p in parts:
            p.unlink()
    print(f"    -> {out_path.relative_to(ROOT)} ({out_path.stat().st_size / 1e6:.1f} MB, {n * n} chunk(s))")


# ---------- main ----------
def build_layers(s1_pass):
    """Return {id: (image, style, ground_resolution_m, scene_count or None)} lazily as lambdas."""
    L = {}
    for s in ["2015_16", "2018_19", "2021_22", "2024_25"]:
        L[f"l8_truecolor_{s}"] = lambda s=s: (*landsat8(s), "truecolor", 30)
    L["l8_ndvi_2015_16"] = lambda: (ndvi(landsat8("2015_16")[0]), None, "ndvi", 30)
    L["l8_ndvi_2024_25"] = lambda: (ndvi(landsat8("2024_25")[0]), None, "ndvi", 30)
    L["l8_ndvi_change_2015_16_to_2024_25"] = lambda: (
        ndvi(landsat8("2024_25")[0]).subtract(ndvi(landsat8("2015_16")[0])), None, "ndviChange", 30)
    L["s2_truecolor_2018_19"] = lambda: (*sentinel2("2018_19"), "truecolor", 10)
    L["s2_truecolor_2025_26"] = lambda: (*sentinel2("2025_26"), "truecolor", 10)
    L["s1_vh_2017_18"] = lambda: (*sentinel1_vh("2017_18", s1_pass), "s1", 20)
    L["s1_vh_2025_26"] = lambda: (*sentinel1_vh("2025_26", s1_pass), "s1", 20)
    L["alos_hv_2010"] = lambda: (*alos_hv(2010), "s1", 25)   # same -25..-5 dB grey scale as NISAR HV
    L["alos_hv_2024"] = lambda: (*alos_hv(2024), "s1", 25)
    L["gmw_1996"] = lambda: (mangrove(1996).selfMask(), None, "mangrove", 25)
    L["gmw_2020"] = lambda: (mangrove(2020).selfMask(), None, "mangrove", 25)

    def lossgain():
        m96, m20 = mangrove(1996), mangrove(2020)
        loss = m96.eq(1).And(m20.eq(0))
        gain = m96.eq(0).And(m20.eq(1))
        return loss.add(gain.multiply(2)).selfMask(), None, "lossGain", 25
    L["gmw_lossgain_1996_2020"] = lossgain
    L["water_s2_2025_26"] = lambda: (water().selfMask(), None, "water", 10)  # analysis mask (alpha>0 = water)
    return L


def pick_s1_pass():
    counts = {p: [s1_collection(s, p).size().getInfo() for s in ("2017_18", "2025_26")]
              for p in ("DESCENDING", "ASCENDING")}
    print(f"Sentinel-1 scenes per pass (2017-18, 2025-26): {counts}")
    usable = {p: c for p, c in counts.items() if min(c) > 0}
    if not usable:
        sys.exit("No single Sentinel-1 pass covers both seasons.")
    return max(usable, key=lambda p: min(usable[p]))


def compute_stats(s1_pass):
    area_reg = dict(reducer=ee.Reducer.sum(), geometry=aoi(), scale=25, maxPixels=1e10)
    mean_reg = dict(reducer=ee.Reducer.mean(), geometry=aoi(), maxPixels=1e10)

    def area(mask):
        return ee.Image.pixelArea().divide(1e6).updateMask(mask).reduceRegion(**area_reg).values().get(0)

    def mean_in(img, mask, scale):
        return img.updateMask(mask).reduceRegion(scale=scale, **mean_reg).values().get(0)

    years = [1996, 2007, 2010, 2020]
    ndvi_seasons = ["2015_16", "2018_19", "2021_22", "2024_25"]
    s1_seasons = ["2017_18", "2025_26"]
    m96, m20 = mangrove(1996), mangrove(2020)
    mmask = m20.eq(1)
    # One request at a time: the free Community tier rejects many parallel aggregations.
    def get(value, label):
        for attempt in range(5):
            try:
                v = value.getInfo()
                print(f"    {label}: {v}")
                return v
            except ee.EEException as e:
                if "concurrent" not in str(e).lower() or attempt == 4:
                    raise
                time.sleep(10 * (attempt + 1))

    d = {
        "area": [get(area(mangrove(y).eq(1)), f"mangrove area {y}") for y in years],
        "gain": get(area(m96.eq(0).And(m20.eq(1))), "gain"),
        "loss": get(area(m96.eq(1).And(m20.eq(0))), "loss"),
        "stable": get(area(m96.eq(1).And(m20.eq(1))), "stable"),
        "ndvi": [get(mean_in(ndvi(landsat8(s)[0]), mmask, 30), f"ndvi {s}") for s in ndvi_seasons],
        "s1": [get(mean_in(sentinel1_vh(s, s1_pass)[0], mmask, 20), f"s1 {s}") for s in s1_seasons],
    }
    r = lambda x, n=2: None if x is None else round(x, n)
    pretty = lambda s: s.replace("_", "–")
    return {
        "status": "ready",
        "generated": dt.date.today().isoformat(),
        "aoi": f"Karachi mangrove coast, Rehri Goth to Port Qasim ({BBOX[0]}–{BBOX[2]}°E, {BBOX[1]}–{BBOX[3]}°N, about 28 × 17.5 km)",
        "mangrove_area": {
            "source": "Global Mangrove Watch v3 extent; area computed by CoastLens within the AOI at 25 m",
            "unit": "km2",
            "years": [{"year": y, "km2": r(v)} for y, v in zip(years, d["area"])],
        },
        "mangrove_change": {
            "from": 1996, "to": 2020,
            "source": "Global Mangrove Watch v3, 1996 vs 2020 map differencing (includes mapping error)",
            "gain_km2": r(d["gain"]), "loss_km2": r(d["loss"]), "stable_km2": r(d["stable"]),
        },
        "ndvi_in_mangroves": {
            "source": "Landsat 8 C2 L2, Nov–Feb cloud-masked median; mean NDVI inside GMW 2020 mangrove extent",
            "series": [{"season": pretty(s), "mean": r(v, 3)} for s, v in zip(ndvi_seasons, d["ndvi"])],
        },
        "s1_vh_in_mangroves": {
            "source": f"Sentinel-1 GRD VH ({s1_pass}), Nov–Feb median, 30 m focal median; mean dB inside GMW 2020 mangrove extent",
            "series": [{"season": pretty(s), "mean_db": r(v)} for s, v in zip(s1_seasons, d["s1"])],
        },
        "nisar": None,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default="coastlens-momos")
    ap.add_argument("--only", nargs="*", help="layer ids to export")
    ap.add_argument("--stats-only", action="store_true")
    ap.add_argument("--no-stats", action="store_true")
    args = ap.parse_args()

    ee.Initialize(project=args.project)
    RAW.mkdir(parents=True, exist_ok=True)
    s1_pass = pick_s1_pass()
    print(f"Using Sentinel-1 {s1_pass} pass")

    if not args.stats_only:
        layers = build_layers(s1_pass)
        ids = args.only or list(layers)
        report = {}
        for lid in ids:
            image, count, style, res = layers[lid]()
            n = count.getInfo() if count is not None else None
            print(f"[{lid}] {res} m" + (f", {n} scenes" if n is not None else ""))
            if n == 0:
                print("    SKIPPED: no scenes in this period")
                continue
            download(rgba(image, STYLE[style]), RAW / f"{lid}.tif", res)
            report[lid] = {"resolution_m": res, "scenes": n}
        (RAW / "export_report.json").write_text(json.dumps({"s1_pass": s1_pass, "layers": report}, indent=2))

    if not args.no_stats:
        print("Computing statistics…")
        stats = compute_stats(s1_pass)
        # merge: keep sections written by the NISAR / GMW scripts
        old = json.loads(STATS_PATH.read_text(encoding="utf-8")) if STATS_PATH.exists() else {}
        stats = old | {k: v for k, v in stats.items() if not (k == "nisar" and v is None and old.get("nisar"))}
        STATS_PATH.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {STATS_PATH.relative_to(ROOT)}")
        print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
