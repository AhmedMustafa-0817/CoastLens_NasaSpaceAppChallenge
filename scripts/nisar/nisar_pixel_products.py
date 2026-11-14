"""NISAR map products for the study box, from the per-pixel stack (nisar_pixel_stack.py).

  nisar_hv_<date>, nisar_hh_<date>   single-pass backscatter (grey; HV -25..-5 dB, HH -20..0 dB)
  nisar_hv_change_<d1>_<d2>          HV difference between two passes (red weaker, blue stronger)
  nisar_classes_2025_26              land-cover map from simple, explainable thresholds on a year of HV/HH
                                     (quad-pol passes only): 1 water / mudflat, 2 mangrove, 3 built-up, 4 other land
  nisar_ai_mangrove_2025_26          AI model (Random Forest) that learned "what mangrove looks like to NISAR"
                                     from Global Mangrove Watch labels, then maps mangrove probability from
                                     NISAR alone. Accuracy is measured on 2 km map blocks the model never saw.
  nisar_hv_trend_2025_26             "forest watch": each mangrove pixel's HV trend relative to the forest
                                     median on every pass. Only shifts common to the whole forest cancel (such as
                                     calibration); a pixel whose seasonal or tidal response differs from the
                                     forest's still gets a slope. Forest mask = GMW 2025, independent of the
                                     tested year. Imaging mode is a covariate. Faded if |t| < 2. A date-shuffle
                                     test measures how much random noise alone would flag.
  nisar_change_type_2025_26          structural vs moisture change (challenge objective): early (Nov-Dec 2025)
                                     vs late (Aug-Oct 2026) quad-pol passes. Moisture/flooding changes HH and HV
                                     together (HV-HH stays put); structural change (canopy loss or growth) moves
                                     HV much more than HH, so HV-HH changes.

Imaging modes: track 164 alternates quad-pol (2005_QPDH, 20 m) and dual-pol (4005_DHDH, 10 m) passes. On the same
20 m grid a dual-pol pass reads differently from its quad-pol neighbours, and the offset depends on the surface
(stats.json > nisar_pixel.mode_offset), so one correction constant would not do. Everything that uses HH or a
yearly mean therefore uses quad-pol passes only; the HV trend uses every pass with the mode as a covariate.

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
TIDE = ROOT / "docs" / "tide_at_pass.csv"   # date, time_utc, tide_m, source (optional; adds a tide term to the trend)
CLASSES = {1: ("Water / mudflat", (29, 111, 224)), 2: ("Mangrove", (24, 160, 88)),
           3: ("Built-up", (230, 57, 70)), 4: ("Other land", (214, 180, 120))}
CHANGE = {1: ("Canopy loss (structural)", (200, 30, 40)), 2: ("Canopy gain (structural)", (30, 150, 70)),
          3: ("Wetter / flooded (moisture)", (40, 110, 230)), 4: ("Drier (moisture)", (240, 160, 40))}
TREND_LIM = 3.0  # dB / year, colour scale limit
WEAK = -1.0      # dB / year relative to forest = "weakening"
SINGLE = {"hv": ["20251121", "20261011"], "hh": ["20261011"]}
GREY = {"hv": (-25, -5), "hh": (-20, 0)}   # HH is much brighter than HV: with the HV range, land clips to white
CHANGE_PAIR = ("20251121", "20261011")
EARLY = ("20251101", "20251231")   # change-type windows (inclusive, yyyymmdd); quad-pol passes only
LATE = ("20260820", "20261031")
BLOCK_PX = 100                     # 2 km blocks for spatial cross-validation
N_SHUFFLE = 20                     # date-shuffle runs for the trend's false-flag rate
RED, WHITE, BLUE = (200, 40, 40), (245, 245, 240), (30, 100, 200)   # every change layer: red = down, blue = up
AUX = OUT / "trend_aux_2025_26.npz"  # t statistics and shuffled flags, read by the monitor


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


def near(mask, k=7):
    """True within k // 2 pixels of mask."""
    return box(mask.astype("float32"), k) > 0


def trend_fit(Y, X):
    """Per-pixel least squares of Y (dates x pixels, dB relative to the forest median; NaN = missing) on the
    columns of X = [1, time in years, dual-pol flag, (tide height)]. The mode term absorbs any leftover quad/dual
    offset. The t statistic of the time slope is deflated for lag-1 autocorrelation of the residuals:
    n_eff = n (1 - r) / (1 + r). Returns slope (dB/yr), t, standard error."""
    X = np.asarray(X, "float64")
    k = X.shape[1]
    ok = np.isfinite(Y)
    n = ok.sum(0)
    A = np.einsum("dp,di,dj->pij", ok.astype("float64"), X, X)
    b = np.einsum("dp,di->pi", np.where(ok, Y, 0).astype("float64"), X)
    bad = (n < 10) | (np.linalg.det(A) < 1e-6)
    A[bad] = np.eye(k)
    Ai = np.linalg.inv(A)
    beta = np.einsum("pij,pj->pi", Ai, b)
    resid = np.where(ok, Y - (X @ beta.T), np.nan)
    ss = np.nansum(resid ** 2, 0)
    se = np.sqrt(ss / np.maximum(n - k, 1) * Ai[:, 1, 1])
    r = np.clip(np.nansum(resid[:-1] * resid[1:], 0) / np.maximum(ss, 1e-9), 0, 0.9)
    n_eff = n * (1 - r) / (1 + r)
    with np.errstate(invalid="ignore", divide="ignore"):
        tstat = beta[:, 1] / (se * np.sqrt(n / n_eff))
    return (np.where(bad, np.nan, beta[:, 1]).astype("float32"), np.where(bad, np.nan, tstat).astype("float32"),
            np.where(bad, np.nan, se).astype("float32"))


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

    all_dates = [Path(f).stem for f in sorted(glob.glob(str(folder / "2*.npz")))]
    files = [f for f in sorted(glob.glob(str(folder / "2*.npz"))) if Path(f).stem not in suspect]
    dates = [Path(f).stem for f in files]
    meta = [np.load(f) for f in files]
    urls = [str(m["url"]) for m in meta]
    quad = np.array(["QP" in str(m["mode"]) for m in meta])   # 2005_QPDH = quad-pol; otherwise 4005_DHDH dual-pol
    maturity = ["beta" if "_BETA_" in u else "provisional" if "_PROVISIONAL_" in u else "validated" for u in urls]
    print(f"{len(dates)} dates ({int(quad.sum())} quad-pol, {int((~quad).sum())} dual-pol), grid {shape}", flush=True)
    raw_hv = np.stack([m["hv"] for m in meta])                # linear power, unfiltered
    raw_hh = np.stack([m["hh"] for m in meta])
    hv = np.stack([box(a) for a in raw_hv])                   # linear power, 3x3 speckle filter (float32)
    hh = np.stack([box(a) for a in raw_hh])
    # yearly means and features: quad-pol passes only, so the two imaging modes are never mixed
    hv_year, hh_year = np.nanmean(hv[quad], 0), np.nanmean(hh[quad], 0)
    HV, HH = 10 * np.log10(hv_year), 10 * np.log10(hh_year)
    ratio = HV - HH
    valid = np.isfinite(HV) & np.isfinite(HH)
    db = 10 * np.log10(hv)
    dbh = 10 * np.log10(hh)
    db_q, dbh_q = db[quad], dbh[quad]

    # ---- 0. single passes + simple change ----
    for pol, arr in (("hv", db), ("hh", dbh)):
        for d in SINGLE[pol]:
            if d in dates:
                write(f"nisar_{pol}_{d}", arr[dates.index(d)], grey(arr[dates.index(d)], *GREY[pol]), tr)
    hh_range = None
    if SINGLE["hh"][0] in dates:
        v = dbh[dates.index(SINGLE["hh"][0])]
        hh_range = {"date": SINGLE["hh"][0], "display_range_db": list(GREY["hh"]),
                    **{f"p{q}_db": round(float(np.nanpercentile(v, q)), 1) for q in (2, 50, 98)}}
    if all(d in dates for d in CHANGE_PAIR):
        dlt = db[dates.index(CHANGE_PAIR[1])] - db[dates.index(CHANGE_PAIR[0])]
        rgba = ramp(dlt, 6.0, [(255, 0, 0), (255, 255, 255), (0, 0, 255)])
        rgba = np.concatenate([rgba, np.where(np.isfinite(dlt), 255, 0).astype("uint8")[..., None]], -1)
        write(f"nisar_hv_change_{CHANGE_PAIR[0]}_{CHANGE_PAIR[1]}", dlt, rgba, tr)

    # ---- 1. land-cover classes from simple thresholds ----
    # texture = spread of the dB values in a 100 m window. Kept in dB on purpose: in dB speckle is additive, so the
    # spread does not grow with brightness (in linear power it would), and the 1.3 dB class rule is defined on it.
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
        tp, fp = int((mask & gm & where).sum()), int((mask & ~gm & where).sum())
        fn, tn = int((~mask & gm & where).sum()), int((~mask & ~gm & where).sum())
        recall, precision = tp / max(tp + fn, 1), tp / max(tp + fp, 1)
        return {
            "gmw_mangrove_found_by_nisar_pct": round(100 * recall, 1),
            "nisar_mangrove_confirmed_by_gmw_pct": round(100 * precision, 1),
            "overall_accuracy_pct": round(100 * (tp + tn) / max(tp + fp + fn + tn, 1), 1),
            "f1": round(2 * precision * recall / max(precision + recall, 1e-9), 2),
            "confusion_pixels": {"both_mangrove": tp, "nisar_only": fp, "gmw_only": fn, "both_not": tn},
            "tested_on": "pixels GMW is sure about (over 90% or under 10% mangrove); mixed edge pixels are left out",
        }

    # ---- imaging-mode offset (measured, not corrected): a pass minus the mean of its two quad-pol neighbours ----
    def mode_offset(lin, m):
        dual_, quad_ = [], []
        for i in range(1, len(dates) - 1):
            if quad[i - 1] and quad[i + 1]:
                d = np.nanmedian(10 * np.log10(lin[i][m]) - 10 * np.log10((lin[i - 1][m] + lin[i + 1][m]) / 2))
                (quad_ if quad[i] else dual_).append(float(d))
        return {"dual_minus_quad_db": round(float(np.mean(dual_)), 2), "spread_db": round(float(np.std(dual_)), 2),
                "dual_passes_compared": len(dual_), "quad_control_db": round(float(np.mean(quad_)), 2)}

    water_px = HV < -20.5
    sd_q = np.maximum(np.nanstd(db_q, 0), np.nanstd(dbh_q, 0))
    surfaces = {"stable land": valid & ~water_px & (ref < 0.1) & ~near(water_px) & (sd_q < 0.7),
                "mangrove": valid & (ref > 0.9) & ~near(water_px, 3),
                "open water": valid & water_px & ~near(~water_px)}
    offsets = {name: {"pixels": int(m.sum()), "HH": mode_offset(raw_hh, m), "HV": mode_offset(raw_hv, m)}
               for name, m in surfaces.items()}
    del raw_hv, raw_hh
    print("mode offset:", json.dumps(offsets), flush=True)

    # ---- 2. AI model: Random Forest on NISAR features, labels from GMW ----
    from sklearn.ensemble import RandomForestClassifier
    hv_std = np.nanstd(db_q, 0)          # how much HV moves through the year (water/tide pixels move a lot)
    hh_std = np.nanstd(dbh_q, 0)
    hv_p10, hv_p90 = np.nanpercentile(db_q, 10, 0), np.nanpercentile(db_q, 90, 0)
    corr_num = np.nanmean((db_q - np.nanmean(db_q, 0)) * (dbh_q - np.nanmean(dbh_q, 0)), 0)
    hvhh_corr = corr_num / (hv_std * hh_std + 1e-6)   # HV and HH rising/falling together = moisture/tide
    feats = {"HV mean": HV, "HH mean": HH, "HV-HH": ratio, "HV texture 100 m": texture,
             "HV seasonal spread": hv_std, "HH seasonal spread": hh_std, "HV low (p10)": hv_p10,
             "HV high (p90)": hv_p90, "HV-HH correlation": hvhh_corr,
             "HV 60 m mean": 10 * np.log10(box(hv_year, 3))}   # averaged in linear power, then dB
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
    # Forest mask for the trend = GMW 2025 (at least half the 20 m pixel). It does not depend on the year being
    # tested. The AI map would: it is built from this year's HV, so a pixel that lost canopy early could drop out
    # of the mask and never be tested.
    fm = valid & (ref >= 0.5)
    dual = (~quad).astype("float32")
    cols = [np.ones_like(t_years), t_years, dual]
    tide = None
    if TIDE.exists():
        import csv
        rows_t = {r["date"].replace("-", ""): float(r["tide_m"]) for r in csv.DictReader(open(TIDE, encoding="utf-8"))}
        if all(d in rows_t for d in dates):
            tide = np.array([rows_t[d] for d in dates], "float32")
            cols.append(tide - tide.mean())
    X = np.stack(cols, 1)

    def relative(mask):
        med = np.array([np.nanmedian(db[i][mask]) for i in range(len(dates))], "float32")
        return db[:, mask] - med[:, None], med

    def flags(sl, ts):
        ok_ = np.isfinite(sl) & (np.abs(ts) >= 2)
        return ok_ & (sl <= WEAK), ok_ & (sl >= -WEAK)

    Y, forest_median = relative(fm)
    sl, ts, se_ = trend_fit(Y, X)
    slope, tstat, se = (np.full(shape, np.nan, "float32") for _ in range(3))
    slope[fm], tstat[fm], se[fm] = sl, ts, se_
    forest = np.isfinite(slope)
    signif = forest & (np.abs(tstat) >= 2)
    rgba = np.zeros(shape + (4,), "uint8")
    rgba[..., :3] = ramp(slope, TREND_LIM, [RED, WHITE, BLUE])
    rgba[..., 3] = np.where(signif, 255, np.where(forest, 70, 0))
    write("nisar_hv_trend_2025_26", slope, rgba, tr)
    weak = signif & (slope <= WEAK)
    strong = signif & (slope >= -WEAK)
    nf = max(int(forest.sum()), 1)

    # How much would noise alone flag? Shuffle the order of the passes (the same shuffle for every pixel, so
    # neighbours keep their shared speckle-filter noise), refit, apply the same rule. This removes any real
    # ordering in time. It does not test season: a seasonal curve is destroyed by the shuffle as well.
    rng_s = np.random.default_rng(7)
    null_weak, null_strong, null_flags = [], [], []
    for _ in range(N_SHUFFLE):
        s_sl, s_ts, _ = trend_fit(Y[rng_s.permutation(len(dates))], X)
        w_, s_ = flags(s_sl, s_ts)
        null_weak.append(100 * float(w_.sum()) / nf)
        null_strong.append(100 * float(s_.sum()) / nf)
        null_flags.append(np.packbits(w_))
    np.savez_compressed(AUX, tstat=tstat, forest=fm, null_weak=np.stack(null_flags), n_forest=int(fm.sum()))
    print(f"shuffle: weak {np.mean(null_weak):.2f}% strong {np.mean(null_strong):.2f}% by chance", flush=True)

    # tide: does the radar follow the predicted water level at each pass?
    tide_stats = None
    if tide is not None:
        def corr(a, b):
            m = np.isfinite(a) & np.isfinite(b)
            return round(float(np.corrcoef(a[m], b[m])[0, 1]), 2)
        med_hh = np.array([np.nanmedian(dbh[i][fm]) for i in range(len(dates))], "float32")
        tc = (tide - tide.mean()).astype("float64")
        Yc = np.nan_to_num(Y - np.nanmean(Y, 0)).astype("float64")
        r_px = (tc @ Yc) / np.sqrt((tc ** 2).sum() * np.maximum((Yc ** 2).sum(0), 1e-9))
        sl2, ts2, _ = trend_fit(Y, X[:, :3])
        w2, s2 = flags(sl2, ts2)
        tide_stats = {
            "source": "docs/tide_at_pass.csv (predicted tide height at each pass)",
            "tide_range_m": [round(float(tide.min()), 2), round(float(tide.max()), 2)],
            "corr_tide_vs_time": corr(tide, t_years),
            "quad_passes": {"corr_tide_forest_median_hv": corr(tide[quad], forest_median[quad]),
                            "corr_tide_forest_median_hh": corr(tide[quad], med_hh[quad]),
                            "corr_tide_forest_median_hv_minus_hh": corr(tide[quad], (forest_median - med_hh)[quad])},
            "pct_forest_pixels_abs_corr_over_0_5": round(100 * float((np.abs(r_px) > 0.5).sum()) / nf, 1),
            "without_tide_term": {"pct_weakening": round(100 * float(w2.sum()) / nf, 1),
                                  "pct_strengthening": round(100 * float(s2.sum()) / nf, 1)},
        }
        r_tide = np.full(shape, np.nan, "float32")
        r_tide[fm] = r_px
        np.savez_compressed(AUX, tstat=tstat, forest=fm, null_weak=np.stack(null_flags), n_forest=int(fm.sum()),
                            r_tide=r_tide)
        print("tide:", json.dumps(tide_stats), flush=True)

    # what the old mask (this year's AI map) would have given, for the record
    Ya, _ = relative(nm)
    a_sl, a_ts, _ = trend_fit(Ya, X)
    a_w, a_s = flags(a_sl, a_ts)
    mask_change = {
        "old_mask": "AI mangrove probability >= 0.5 (built from the same year of HV)",
        "pixels_only_in_old_mask": int((nm & ~fm).sum()), "pixels_only_in_new_mask": int((fm & ~nm).sum()),
        "pixels_in_both": int((nm & fm).sum()),
        "old_mask_pct_weakening": round(100 * float(a_w.sum()) / max(int(np.isfinite(a_sl).sum()), 1), 1),
        "old_mask_pct_strengthening": round(100 * float(a_s.sum()) / max(int(np.isfinite(a_sl).sum()), 1), 1),
        "pct_weakening_in_pixels_the_old_mask_missed": round(100 * float((weak & ~nm).sum()) / max(int((forest & ~nm).sum()), 1), 1),
    }
    del Y, Ya
    near_land = box(((cls == 3) | (cls == 4)).astype("float32"), 7) > 0
    edge, interior = fm & near_land, fm & ~near_land

    # ---- 4. structural vs moisture change ----
    # Quad-pol passes only on both sides (same imaging mode, same processing version), and all averaging and
    # smoothing in linear power; dB only at the end.
    def window_mean(lin, lo, hi):
        idx = [i for i, d in enumerate(dates) if lo <= d <= hi and quad[i]]
        return box(np.nanmean(lin[idx], 0), 3), [dates[i] for i in idx]   # 60 m smoothing to beat speckle

    hv_e, e_dates = window_mean(hv, *EARLY)
    hv_l, l_dates = window_mean(hv, *LATE)
    hh_e, _ = window_mean(hh, *EARLY)
    hh_l, _ = window_mean(hh, *LATE)
    d_hv, d_hh = 10 * np.log10(hv_l / hv_e), 10 * np.log10(hh_l / hh_e)
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
    in_forest = {CHANGE[k][0]: round(100 * float(((ctype == k) & fm).sum() / max(fm.sum(), 1)), 2) for k in CHANGE}

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
            z["status"] = ("radar weakening well above the forest average this year" if ratio_w >= 1.5 and z["pct_forest_weakening"] >= 15 else
                           "watch: radar weakening slightly above the forest average" if ratio_w >= 1.0 else
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
    n_mat = {k: maturity.count(k) for k in ("provisional", "validated", "beta") if maturity.count(k)}
    stats["nisar_pixel"] = {
        "source": f"NISAR L2 GCOV track {args.track}, {len(dates)} dates {dates[0]}-{dates[-1]} "
                  f"(QC-suspect dates removed), HV and HH per pixel on a 20 m grid after a 3x3 speckle filter",
        "passes": {
            "listed": len(all_dates), "used": len(dates),
            "removed_by_quality_check": sorted(d for d in all_dates if d not in dates),
            "quad_pol": int(quad.sum()), "dual_pol": int((~quad).sum()), **n_mat,
            "validated_dates": [d for d, m in zip(dates, maturity) if m == "validated"],
            "quad_pol_dates": [d for d, q in zip(dates, quad) if q],
            "dual_pol_dates": [d for d, q in zip(dates, quad) if not q],
            "years_spanned": round(float(t_years[-1]), 2),
            "summary": f"{len(dates)} passes: " + ", ".join(f"{v} {k}" for k, v in n_mat.items()),
        },
        "mode_offset": {
            "what": "Median over each surface of (a dual-pol pass, dB) minus (the mean of its two quad-pol neighbours, "
                    "averaged in linear power). quad_control_db is the same measure for quad-pol passes between two "
                    "quad-pol passes and should be near zero. Measured on the unfiltered 20 m stack.",
            "surfaces": offsets,
            "handling": "Not corrected: the offset differs by surface, so one constant would not fit. Yearly means, "
                        "the AI features, the land-cover rules and the structural-vs-moisture windows use quad-pol "
                        "passes only. The HV trend uses every pass, relative to the forest median of the same pass, "
                        "with the imaging mode as a covariate.",
        },
        "hh_display": hh_range,
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
            "published_map": "A second model trained on every sure pixel in the box (not the held-out models), "
                             "mangrove = probability >= 0.5",
            "features_from": "quad-pol passes only",
        },
        "trend": {
            "id": "nisar_hv_trend_2025_26",
            "unit": "dB per year, relative to the forest median on each date",
            "forest_mask": "Global Mangrove Watch v4.1 2025, at least half of the 20 m pixel (independent of the tested year)",
            "forest_km2": round(float(fm.sum() * px_km2), 2),
            "weakening_threshold": WEAK,
            "dates_used": len(dates),
            "model": "per pixel: relative HV = a + b*time + m*(dual-pol pass)" + (" + c*tide" if tide is not None else ""),
            "median": round(float(np.median(s)), 2),
            "rule": "weakening = slope <= -1 dB/yr AND |t| >= 2; strengthening likewise; else steady. t = slope / "
                    "standard error, deflated for lag-1 autocorrelation of the residuals (n_eff = n(1-r)/(1+r)). "
                    "Not corrected for season or for testing many pixels.",
            "median_standard_error": round(float(np.nanmedian(se[forest])), 2),
            "pct_weakening": round(100 * float(weak.sum()) / nf, 1),
            "pct_strengthening": round(100 * float(strong.sum()) / nf, 1),
            "pct_stable": round(100 - 100 * float((weak | strong).sum()) / nf, 1),
            "weakening_km2": round(float(weak.sum() * px_km2), 2),
            "pct_weakening_edge": round(100 * float((weak & edge).sum() / max((edge & forest).sum(), 1)), 1),
            "pct_weakening_interior": round(100 * float((weak & interior).sum() / max((interior & forest).sum(), 1)), 1),
            "by_chance": {
                "method": f"{N_SHUFFLE} runs with the order of the passes shuffled (same shuffle for all pixels), "
                          "refitted, same rule. Measures random noise only: a shuffle also destroys any seasonal curve.",
                "pct_weakening": round(float(np.mean(null_weak)), 1),
                "pct_strengthening": round(float(np.mean(null_strong)), 1),
                "pct_weakening_max_run": round(float(np.max(null_weak)), 1),
                "pct_strengthening_max_run": round(float(np.max(null_strong)), 1),
            },
            "mask_change": mask_change,
            "tide": tide_stats,
            "same_season_comparison": "pending: needs Nov-Dec 2026 quad-pol passes to compare with Nov-Dec 2025",
            "caveat": "One year of data: this ranks patches against the rest of the forest, and season-dependent effects "
                      "(tidal flooding, leaf flush, soil moisture) can differ between patches. It is not yet a multi-year trend.",
        },
        "change_type": {
            "id": "nisar_change_type_2025_26",
            "early_dates": e_dates, "late_dates": l_dates,
            "modes": "quad-pol passes only in both windows; averaged and smoothed in linear power",
            "rule": "changed if |dHV| or |dHH| >= 2 dB (60 m smoothed); structural if |dHV - dHH| >= 1.5 dB and |dHV| >= 2 dB "
                    "(cross-pol volume echo moved much more than co-pol = canopy changed); otherwise moisture "
                    "(both moved together = wetter/drier ground or tidal flooding)",
            "area_km2": change_area,
            "pct_of_forest": in_forest,
            "caveat": "Early and late windows are 8 to 11 months apart and not the same season, so moisture changes are expected. "
                      "Structural pixels are candidates for field checks, not confirmed loss.",
        },
        "zones": zone_stats,
        "sensor_comparison": comparison,
    }
    STATS.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in stats["nisar_pixel"].items() if k != "zones"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
