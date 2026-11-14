"""NISAR map products for the study box, from the per-pixel stack (nisar_pixel_stack.py).

  nisar_hv_<date>, nisar_hh_<date>   single-pass backscatter (grey, -25..-5 dB)
  nisar_hv_change_<d1>_<d2>          HV difference between two passes (red weaker, blue stronger)
  nisar_classes_2025_26              land-cover map from simple, explainable thresholds on a year of HV/HH:
                                     1 water / mudflat, 2 mangrove, 3 built-up, 4 other land
  nisar_ai_mangrove_2025_26          AI model (Random Forest) that learned "what mangrove looks like to NISAR"
                                     from Global Mangrove Watch labels, then maps mangrove probability from
                                     NISAR alone. Accuracy is measured on 2 km map blocks the model never saw.
  nisar_hv_trend_2025_26             "forest watch": each mangrove pixel's HV trend relative to the forest
                                     median on every pass (season, tide and calibration cancel), faded if |t| < 2
  nisar_change_type_2025_26          structural vs moisture change (challenge objective): early (Nov-Dec 2025)
                                     vs late (Sep-Oct 2026) passes. Moisture/flooding changes HH and HV together
                                     (HV-HH stays put); structural change (canopy loss or growth) moves HV much
                                     more than HH, so HV-HH changes.

Also: NISAR status inside each GMW decline zone (public/data/zones.geojson), and a sensor comparison
(Landsat NDVI, Sentinel-1 C-band, ALOS-2 L-band vs NISAR) on the same 20 m pixels if
data_raw/ee/older_on_nisar_grid.tif exists (scripts/ee/older_sensors.py --grid).

Writes <id>_value.tif + <id>_rgba.tif to data_raw/nisar/ and stats.json > nisar_pixel.

    python scripts/nisar/nisar_pixel_products.py --track 164
"""

import argparse
import glob
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from shapely import transform as stransform
from shapely.geometry import shape as sshape

sys.path.insert(0, str(Path(__file__).parent))
from nisar_timeseries import EPSG, ROOT, STATS  # noqa: E402

OUT = ROOT / "data_raw" / "nisar"
ZONES = ROOT / "public" / "data" / "zones.geojson"
OLDER = ROOT / "data_raw" / "ee" / "older_on_nisar_grid.tif"
CLASSES = {1: ("Water / mudflat", (29, 111, 224)), 2: ("Mangrove", (24, 160, 88)),
           3: ("Built-up", (230, 57, 70)), 4: ("Other land", (214, 180, 120))}
CHANGE = {1: ("Canopy loss (structural)", (200, 30, 40)), 2: ("Canopy gain (structural)", (30, 150, 70)),
          3: ("Wetter / flooded (moisture)", (40, 110, 230)), 4: ("Drier (moisture)", (240, 160, 40))}
TREND_LIM = 3.0  # dB / year, colour scale limit
WEAK = -1.0      # dB / year relative to forest = "weakening"
SINGLE = {"hv": ["20251121", "20261011"], "hh": ["20261011"]}
CHANGE_PAIR = ("20251121", "20261011")
EARLY = ("20251101", "20251231")   # change-type windows (inclusive, yyyymmdd)
LATE = ("20260901", "20261031")
BLOCK_PX = 100                     # 2 km blocks for spatial cross-validation


def box(a, k=3):
    """k x k moving mean ignoring NaN (speckle filter, no scipy)."""
    p = k // 2
    v = np.pad(np.nan_to_num(a), p, mode="edge").astype("float32")
    n = np.pad(np.isfinite(a).astype("float32"), p, mode="edge")
    s = sum(v[i:i + a.shape[0], j:j + a.shape[1]] for i in range(k) for j in range(k))
    c = sum(n[i:i + a.shape[0], j:j + a.shape[1]] for i in range(k) for j in range(k))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan).astype("float32")


def write(id_, value, rgba, transform, dtype="float32", nodata=np.nan):
    prof = dict(driver="GTiff", height=value.shape[0], width=value.shape[1], crs=CRS.from_epsg(EPSG),
                transform=transform, compress="deflate")
    with rasterio.open(OUT / f"{id_}_value.tif", "w", count=1, dtype=dtype, nodata=nodata, **prof) as d:
        d.write(value.astype(dtype), 1)
    with rasterio.open(OUT / f"{id_}_rgba.tif", "w", count=4, dtype="uint8", **prof) as d:
        d.write(rgba.transpose(2, 0, 1))
    print("wrote", OUT / f"{id_}_rgba.tif", flush=True)


def ramp(x, lim, colors):
    """3-colour diverging ramp: colors[0] at -lim, colors[1] at 0, colors[2] at +lim."""
    t = np.clip(np.nan_to_num(x) / lim, -1, 1)
    lo, mid, hi = (np.array(c, "float32") for c in colors)
    neg = mid + (lo - mid) * (-t)[..., None]
    pos = mid + (hi - mid) * t[..., None]
    return np.where((t < 0)[..., None], neg, pos).astype("uint8")


def grey(db, vmin=-25, vmax=-5):
    g = (np.clip((db - vmin) / (vmax - vmin), 0, 1) * 255).astype("uint8")
    rgba = np.stack([g, g, g, np.where(np.isfinite(db), 255, 0).astype("uint8")], -1)
    return rgba


def paint(cls, palette):
    rgba = np.zeros(cls.shape + (4,), "uint8")
    for k, (_, col) in palette.items():
        rgba[cls == k] = (*col, 255)
    return rgba


def auc(score, label):
    """Area under the ROC curve (rank-based, ties averaged)."""
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(label, score))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--track", type=int, default=164)
    args = ap.parse_args()
    warnings.simplefilter("ignore", RuntimeWarning)

    folder = OUT / f"stack_{args.track}"
    grid = json.loads((folder / "grid.json").read_text())
    tr, shape = Affine(*grid["transform"]), tuple(grid["shape"])
    px_km2 = abs(tr.a * tr.e) / 1e6
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    suspect = {d.replace("-", "") for d in stats.get("nisar_timeseries", {}).get("qc_suspect_dates", [])}

    files = [f for f in sorted(glob.glob(str(folder / "2*.npz"))) if Path(f).stem not in suspect]
    dates = [Path(f).stem for f in files]
    print(f"{len(dates)} dates, grid {shape}", flush=True)
    hv = np.stack([box(np.load(f)["hv"]) for f in files])  # linear power, speckle-filtered (float32)
    hh = np.stack([box(np.load(f)["hh"]) for f in files])
    HV, HH = 10 * np.log10(np.nanmean(hv, 0)), 10 * np.log10(np.nanmean(hh, 0))
    ratio = HV - HH
    valid = np.isfinite(HV) & np.isfinite(HH)
    db = 10 * np.log10(hv)
    dbh = 10 * np.log10(hh)

    # ---- 0. single passes + simple change ----
    for pol, arr in (("hv", db), ("hh", dbh)):
        for d in SINGLE[pol]:
            if d in dates:
                write(f"nisar_{pol}_{d}", arr[dates.index(d)], grey(arr[dates.index(d)]), tr)
    if all(d in dates for d in CHANGE_PAIR):
        dlt = db[dates.index(CHANGE_PAIR[1])] - db[dates.index(CHANGE_PAIR[0])]
        rgba = ramp(dlt, 6.0, [(255, 0, 0), (255, 255, 255), (0, 0, 255)])
        rgba = np.concatenate([rgba, np.where(np.isfinite(dlt), 255, 0).astype("uint8")[..., None]], -1)
        write(f"nisar_hv_change_{CHANGE_PAIR[0]}_{CHANGE_PAIR[1]}", dlt, rgba, tr)

    # ---- 1. land-cover classes from simple thresholds ----
    texture = np.sqrt(np.maximum(box(HV ** 2, 5) - box(HV, 5) ** 2, 0))
    cls = np.zeros(shape, "uint8")
    water = HV < -20.5
    built = ~water & ((HH > -3.5) | (ratio < -10.0) | (HV > -10.5))
    mang_rule = ~water & ~built & (HV >= -19.0) & (ratio >= -8.0) & (texture < 1.3)
    cls[valid & water] = 1
    cls[valid & mang_rule] = 2
    cls[valid & built] = 3
    cls[valid & (cls == 0)] = 4
    write("nisar_classes_2025_26", cls, paint(cls, CLASSES), tr, dtype="uint8", nodata=0)
    area = {CLASSES[k][0]: round(float((cls == k).sum() * px_km2), 2) for k in CLASSES}

    # ---- reference labels: GMW v4.1 2025 fraction per 20 m pixel ----
    gmw_v4 = sorted(p for p in glob.glob(str(ROOT / "data_raw" / "gmw_v4" / "**" / "*N25E067*.tif"), recursive=True)
                    if not Path(p).name.startswith("._"))
    with rasterio.open(gmw_v4[0]) as s:
        ref = np.zeros(shape, "float32")
        reproject((s.read(s.count) == 1).astype("float32"), ref, src_transform=s.transform, src_crs=s.crs,
                  dst_transform=tr, dst_crs=CRS.from_epsg(EPSG), resampling=Resampling.average)
    sure = valid & ((ref > 0.9) | (ref < 0.1))
    gm = ref > 0.9

    def agreement(mask, where):
        tp = (mask & gm & where).sum()
        return {
            "gmw_mangrove_found_by_nisar_pct": round(100 * float(tp / max((gm & where).sum(), 1)), 1),
            "nisar_mangrove_confirmed_by_gmw_pct": round(100 * float(tp / max((mask & where).sum(), 1)), 1),
            "overall_accuracy_pct": round(100 * float(((mask == gm) & where).sum() / max(where.sum(), 1)), 1),
        }

    # ---- 2. AI model: Random Forest on NISAR features, labels from GMW ----
    from sklearn.ensemble import RandomForestClassifier
    hv_std = np.nanstd(db, 0)            # how much HV moves through the year (water/tide pixels move a lot)
    hh_std = np.nanstd(dbh, 0)
    hv_p10, hv_p90 = np.nanpercentile(db, 10, 0), np.nanpercentile(db, 90, 0)
    corr_num = np.nanmean((db - np.nanmean(db, 0)) * (dbh - np.nanmean(dbh, 0)), 0)
    hvhh_corr = corr_num / (hv_std * hh_std + 1e-6)   # HV and HH rising/falling together = moisture/tide
    feats = {"HV mean": HV, "HH mean": HH, "HV-HH": ratio, "HV texture 100 m": texture,
             "HV seasonal spread": hv_std, "HH seasonal spread": hh_std, "HV low (p10)": hv_p10,
             "HV high (p90)": hv_p90, "HV-HH correlation": hvhh_corr, "HV 60 m mean": box(HV, 3)}
    X = np.stack([np.nan_to_num(f, nan=-99) for f in feats.values()], -1).reshape(-1, len(feats))
    y = gm.ravel()
    rows, cols = np.indices(shape)
    block = ((rows // BLOCK_PX + cols // BLOCK_PX) % 2).ravel()   # checkerboard of 2 km blocks
    lab = sure.ravel()
    rng = np.random.default_rng(42)

    def fit(idx):
        idx = rng.choice(idx, min(len(idx), 150_000), replace=False)
        m = RandomForestClassifier(n_estimators=150, max_depth=14, min_samples_leaf=5, n_jobs=-1, random_state=0,
                                   class_weight="balanced_subsample")
        return m.fit(X[idx], y[idx])

    # spatial cross-validation: train on one colour of the checkerboard, test on the other, and vice versa
    prob_cv = np.zeros(X.shape[0], "float32")
    for b in (0, 1):
        m = fit(np.nonzero(lab & (block == b))[0])
        test = np.nonzero(block != b)[0]
        prob_cv[test] = m.predict_proba(X[test])[:, 1]
    ai_cv = (prob_cv.reshape(shape) >= 0.5) & valid
    ai_acc = agreement(ai_cv, sure)
    rule_acc = agreement(mang_rule & valid, sure)
    print("AI (held-out blocks):", ai_acc, "\nthreshold rules:", rule_acc, flush=True)
    model = fit(np.nonzero(lab)[0])
    prob = model.predict_proba(X)[:, 1].reshape(shape).astype("float32")
    prob[~valid] = np.nan
    importance = sorted(zip(feats, model.feature_importances_), key=lambda t: -t[1])
    green = np.array([10, 140, 60], "float32")
    pale = np.array([255, 255, 210], "float32")
    t = np.clip(np.nan_to_num(prob), 0, 1)[..., None]
    rgba = np.zeros(shape + (4,), "uint8")
    rgba[..., :3] = (pale * (1 - t) + green * t).astype("uint8")
    rgba[..., 3] = np.where(np.nan_to_num(prob) >= 0.2, (80 + 175 * t[..., 0]).astype("uint8"), 0)
    write("nisar_ai_mangrove_2025_26", prob, rgba, tr)
    nm = (prob >= 0.5) & valid      # NISAR mangrove mask used below

    # ---- 3. forest watch: relative HV trend inside the forest ----
    d0 = np.datetime64(f"{dates[0][:4]}-{dates[0][4:6]}-{dates[0][6:]}")
    t_years = np.array([(np.datetime64(f"{d[:4]}-{d[4:6]}-{d[6:]}") - d0) / np.timedelta64(1, "D") / 365.25
                        for d in dates], "float32")
    forest_median = np.array([np.nanmedian(db[i][nm]) for i in range(len(dates))], "float32")
    rel = db - forest_median[:, None, None]
    ok = np.isfinite(rel)
    n = ok.sum(0)
    tm = np.where(ok, t_years[:, None, None], np.nan)
    tbar, ybar = np.nanmean(tm, 0), np.nanmean(rel, 0)
    sxx = np.nansum((tm - tbar) ** 2, 0)
    slope = np.nansum((tm - tbar) * (rel - ybar), 0) / sxx
    resid = rel - (ybar + slope * (tm - tbar))
    se = np.sqrt(np.nansum(resid ** 2, 0) / np.maximum(n - 2, 1) / sxx)
    del tm, resid, rel
    tstat = slope / se
    slope = np.where(nm & (n >= 10), slope, np.nan)
    signif = np.isfinite(slope) & (np.abs(tstat) >= 2)
    rgba = np.zeros(shape + (4,), "uint8")
    rgba[..., :3] = ramp(slope, TREND_LIM, [(200, 40, 40), (245, 245, 240), (30, 150, 70)])
    rgba[..., 3] = np.where(signif, 255, np.where(np.isfinite(slope), 70, 0))
    write("nisar_hv_trend_2025_26", slope, rgba, tr)
    weak = signif & (slope <= WEAK)
    strong = signif & (slope >= -WEAK)
    forest = np.isfinite(slope)
    nf = max(int(forest.sum()), 1)
    near_land = box(((cls == 3) | (cls == 4)).astype("float32"), 7) > 0
    edge, interior = nm & near_land, nm & ~near_land

    # ---- 4. structural vs moisture change ----
    def window_mean(arr, lo, hi):
        idx = [i for i, d in enumerate(dates) if lo <= d <= hi]
        return 10 * np.log10(np.nanmean(10 ** (arr[idx] / 10), 0)), [dates[i] for i in idx]

    hv_e, e_dates = window_mean(db, *EARLY)
    hv_l, l_dates = window_mean(db, *LATE)
    hh_e, _ = window_mean(dbh, *EARLY)
    hh_l, _ = window_mean(dbh, *LATE)
    d_hv, d_hh = box(hv_l - hv_e, 3), box(hh_l - hh_e, 3)   # 60 m smoothing to beat speckle
    d_ratio = d_hv - d_hh
    changed = (np.abs(d_hv) >= 2.0) | (np.abs(d_hh) >= 2.0)
    structural = changed & (np.abs(d_ratio) >= 1.5) & (np.abs(d_hv) >= 2.0)
    moisture = changed & ~structural
    ctype = np.zeros(shape, "uint8")
    ctype[structural & (d_hv < 0)] = 1
    ctype[structural & (d_hv > 0)] = 2
    ctype[moisture & ((d_hv + d_hh) > 0)] = 3
    ctype[moisture & ((d_hv + d_hh) <= 0)] = 4
    ctype[~valid | (cls == 1)] = 0   # open water / mudflat: waves and tides, not canopy
    write("nisar_change_type_2025_26", ctype, paint(ctype, CHANGE), tr, dtype="uint8", nodata=0)
    land = valid & (cls != 1)
    change_area = {CHANGE[k][0]: round(float((ctype == k).sum() * px_km2), 2) for k in CHANGE}
    in_forest = {CHANGE[k][0]: round(100 * float(((ctype == k) & nm).sum() / max(nm.sum(), 1)), 2) for k in CHANGE}

    # ---- 5. NISAR status inside each decline zone ----
    zone_stats = []
    if ZONES.exists():
        to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{EPSG}", always_xy=True)
        gj = json.loads(ZONES.read_text(encoding="utf-8"))
        # baseline rates over all NISAR forest, for comparison
        base_weak = 100 * float(weak.sum()) / nf
        for f in gj["features"]:
            g = stransform(sshape(f["geometry"]), lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
            zm = rasterize([(g, 1)], out_shape=shape, transform=tr, fill=0, all_touched=False).astype(bool) & valid
            zf = zm & forest
            nz = max(int(zf.sum()), 1)
            p = f["properties"]
            z = {
                "id": p["id"],
                "nisar_mangrove_km2": round(float((zm & nm).sum() * px_km2), 3),
                "gmw_2025_km2": p["km2_2025"],
                "pct_forest_weakening": round(100 * float((weak & zf).sum()) / nz, 1),
                "pct_forest_strengthening": round(100 * float((strong & zf).sum()) / nz, 1),
                "median_trend_db_per_year": round(float(np.nanmedian(slope[zf])), 2) if zf.any() else None,
                "pct_canopy_loss_structural": round(100 * float(((ctype == 1) & zm & land).sum() / max((zm & land).sum(), 1)), 1),
                "pct_wetter_moisture": round(100 * float(((ctype == 3) & zm & land).sum() / max((zm & land).sum(), 1)), 1),
                "box_pct_forest_weakening": round(base_weak, 1),
            }
            ratio_w = z["pct_forest_weakening"] / max(base_weak, 0.1)
            z["status"] = ("still declining now (NISAR)" if ratio_w >= 1.5 and z["pct_forest_weakening"] >= 15 else
                           "watch: some weakening" if ratio_w >= 1.0 else
                           "no extra weakening seen by NISAR this year")
            zone_stats.append(z)
            p.update({k: v for k, v in z.items() if k != "id"})
            print("zone", z, flush=True)
        ZONES.write_text(json.dumps(gj) + "\n", encoding="utf-8")

    # ---- 6. sensor comparison on the same pixels (held-out blocks) ----
    comparison = None
    if OLDER.exists():
        with rasterio.open(OLDER) as s:
            older = {s.descriptions[i] or f"b{i}": s.read(i + 1) for i in range(s.count)}
        test = sure & (np.isfinite(HV))
        rows_ = []
        cand = [
            ("Landsat 8/9 NDVI (optical, 30 m, 2025-26)", older.get("ndvi_2025_26"), "optical"),
            ("Sentinel-1 VH (C-band radar, 2025-26)", older.get("s1_vh_2025_26"), "C-band"),
            ("ALOS-2 PALSAR-2 HV (L-band, 2024 mosaic)", older.get("alos_hv_2024"), "L-band (old)"),
            ("NISAR HV, year mean (L-band, 2025-26)", HV, "NISAR"),
            ("NISAR AI model (10 radar features, held-out blocks)", prob_cv.reshape(shape), "NISAR"),
        ]
        for name, arr, kind in cand:
            if arr is None:
                continue
            m = test & np.isfinite(arr)
            rows_.append({"sensor": name, "kind": kind, "auc": round(auc(arr[m], gm[m]), 3),
                          "pixels": int(m.sum())})
        comparison = {
            "what": "How well each sensor alone separates mangrove from non-mangrove on the same 20 m pixels "
                    "(AUC: 0.5 = coin flip, 1.0 = perfect). Labels: pixels that GMW v4.1 2025 calls clearly "
                    "mangrove (>90%) or clearly not (<10%).",
            "caveat": "GMW is itself built from Landsat and ALOS, so this comparison is tilted in favour of the "
                      "older sensors. NISAR still has to match it without any optical input.",
            "results": rows_,
        }
        for r in rows_:
            print("AUC", r, flush=True)

    # ---- 7. mangrove vs open water on the headline passes (Insights page cards) ----
    water_tif = ROOT / "data_raw" / "ee" / "water_s2_2025_26.tif"
    if water_tif.exists():
        with rasterio.open(water_tif) as w:
            wat = np.zeros(shape, "float32")
            reproject((w.read(4) > 0).astype("float32"), wat, src_transform=w.transform, src_crs=w.crs,
                      dst_transform=tr, dst_crs=CRS.from_epsg(EPSG), resampling=Resampling.average)
        open_water = valid & (wat > 0.9)
        cards = []
        for pol, lin in (("HV", hv), ("HH", hh)):
            for d in SINGLE[pol.lower()]:
                if d not in dates:
                    continue
                a = lin[dates.index(d)]
                m, wm = gm & np.isfinite(a), open_water & np.isfinite(a)
                cards.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]} {pol}", "pol": pol,
                              "mean_db": round(float(10 * np.log10(np.nanmean(a[m]))), 2),
                              "water_db": round(float(10 * np.log10(np.nanmean(a[wm]))), 2), "n": int(m.sum())})
        stats["nisar"] = {
            "source": f"NISAR L2 GCOV track {args.track} descending, frame 76, on a 20 m grid (provisional products). "
                      "Mean of linear power inside Global Mangrove Watch v4.1 2025 mangroves; water = Sentinel-2 MNDWI mask.",
            "series": cards,
        }

    s = slope[forest]
    stats["nisar_pixel"] = {
        "source": f"NISAR L2 GCOV track {args.track}, {len(dates)} dates {dates[0]}-{dates[-1]} "
                  f"(QC-suspect dates removed), HV and HH per pixel on a 20 m grid after a 3x3 speckle filter",
        "classes": {
            "id": "nisar_classes_2025_26",
            "rules_db": "water/mudflat: HV < -20.5; built-up: HH > -3.5 or HV-HH < -10 or HV > -10.5; "
                        "mangrove: HV >= -19, HV-HH >= -8 and 100 m HV texture < 1.3 dB; other land: the rest",
            "area_km2": area,
            "agreement": rule_acc | {"reference": "Global Mangrove Watch v4.1, 2025",
                                     "gmw_mangrove_km2": round(float((ref * valid).sum() * px_km2), 2)},
        },
        "ai": {
            "id": "nisar_ai_mangrove_2025_26",
            "model": "Random Forest (150 trees) on 10 NISAR-only features per 20 m pixel",
            "features_by_importance": [{"feature": k, "importance": round(float(v), 3)} for k, v in importance],
            "trained_on": "Global Mangrove Watch v4.1 2025 labels (pixels clearly mangrove or clearly not)",
            "validation": "2 km checkerboard blocks: trained on half the map, tested on the other half, and swapped",
            "held_out_accuracy": ai_acc,
            "threshold_rules_accuracy_same_pixels": rule_acc,
            "mangrove_km2": round(float(nm.sum() * px_km2), 2),
        },
        "trend": {
            "id": "nisar_hv_trend_2025_26",
            "unit": "dB per year, relative to the forest median on each date",
            "forest_mask": "AI mangrove probability >= 0.5",
            "weakening_threshold": WEAK,
            "dates_used": len(dates),
            "median": round(float(np.median(s)), 2),
            "rule": "weakening = slope <= -1 dB/yr AND |t| >= 2 (slope/standard error); strengthening likewise; else steady",
            "median_standard_error": round(float(np.nanmedian(se[forest])), 2),
            "pct_weakening": round(100 * float(weak.sum()) / nf, 1),
            "pct_strengthening": round(100 * float(strong.sum()) / nf, 1),
            "pct_stable": round(100 - 100 * float((weak | strong).sum()) / nf, 1),
            "weakening_km2": round(float(weak.sum() * px_km2), 2),
            "pct_weakening_edge": round(100 * float((weak & edge).sum() / max((edge & forest).sum(), 1)), 1),
            "pct_weakening_interior": round(100 * float((weak & interior).sum() / max((interior & forest).sum(), 1)), 1),
            "caveat": "One year of data: this ranks patches against the rest of the forest, and season-dependent effects "
                      "(tidal flooding, leaf flush, soil moisture) can differ between patches. It is not yet a multi-year trend.",
        },
        "change_type": {
            "id": "nisar_change_type_2025_26",
            "early_dates": e_dates, "late_dates": l_dates,
            "rule": "changed if |dHV| or |dHH| >= 2 dB (60 m smoothed); structural if |dHV - dHH| >= 1.5 dB and |dHV| >= 2 dB "
                    "(cross-pol volume echo moved much more than co-pol = canopy changed); otherwise moisture "
                    "(both moved together = wetter/drier ground or tidal flooding)",
            "area_km2": change_area,
            "pct_of_forest": in_forest,
            "caveat": "Early and late windows are ~10 months apart and not the same season, so moisture changes are expected. "
                      "Structural pixels are candidates for field checks, not confirmed loss.",
        },
        "zones": zone_stats,
        "sensor_comparison": comparison,
    }
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in stats["nisar_pixel"].items() if k != "zones"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
