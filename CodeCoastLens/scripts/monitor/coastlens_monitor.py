"""CoastLens monitor: watches the mangroves with every new NISAR pass and tells NGOs where to look.

NISAR passes over Karachi every 12 days (track 164). Each run:
  1. refresh   ask ASF (asf_search) for new NISAR GCOV/GUNW files over the box and add them to
               docs/nisar_scenes_rehri_goth.csv
  2. update    read the new passes (nisar_pixel_stack.py) and rebuild the NISAR products
               (nisar_pixel_products.py: AI mangrove map, forest watch, structural vs moisture change)
  3. alerts    find patches of mangrove whose radar signal weakened this year compared with the rest of the
               forest (the entry condition), check each against older, different records, and write
                 public/data/places.geojson   alert pins on the map
                 public/data/alerts.json      machine-readable feed (for an app, SMS or e-mail bot)
                 docs/alerts/latest.md        a plain-language bulletin an NGO can read or forward

    python scripts/monitor/coastlens_monitor.py              # all three steps
    python scripts/monitor/coastlens_monitor.py --alerts     # only rebuild alerts from existing products

An alert says "the radar signal weakened here", never "the mangrove is thinning": the cause is not known until
someone looks. The feed also says how many alerts random noise alone would raise (from the date-shuffled trend
maps written by nisar_pixel_products.py) and how common each supporting record is across the whole forest.
"""

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import glob

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.warp import reproject
from shapely import transform as stransform
from shapely.geometry import shape as sshape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nisar"))
from nisar_pixel_products import box  # noqa: E402  (3x3 moving mean)

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
CSV_PATH = ROOT / "docs" / "nisar_scenes_rehri_goth.csv"
NISAR = ROOT / "data_raw" / "nisar"
DATA = ROOT / "public" / "data"
STATS = DATA / "stats.json"
ZONES = DATA / "zones.geojson"
PLACES = DATA / "places.geojson"
ALERTS = DATA / "alerts.json"
EE = ROOT / "data_raw" / "ee"
OLDER = EE / "older_on_nisar_grid.tif"
BULLETIN = ROOT / "docs" / "alerts" / "latest.md"
BBOX = (67.155304, 24.671376, 67.433395, 24.828817)
TRACK = 164
REPEAT_DAYS = 12
CELL = 5            # 5 x 20 m = 100 m cells
MAX_ALERTS = 8


# ---------------- 1. refresh scene list ----------------
def refresh():
    import asf_search as asf
    l, b, r, t = BBOX
    wkt = f"POLYGON(({l} {b},{r} {b},{r} {t},{l} {t},{l} {b}))"
    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    known = {row["file"] for row in rows}
    last = max(row["start_utc"] for row in rows)[:10]
    new = []
    for level in ("GCOV", "GUNW"):
        for g in asf.search(dataset="NISAR", intersectsWith=wkt, processingLevel=level, start=last):
            p = g.properties
            url = p.get("url", "")
            name = url.rsplit("/", 1)[-1]
            if not name.endswith(".h5") or name in known:
                continue
            new.append({"product": level, "start_utc": p["startTime"][:19], "direction": p.get("flightDirection", ""),
                        "track": str(p.get("pathNumber", "")), "frame": str(p.get("frameNumber", "")),
                        "polarizations": "/".join(p.get("polarization") or []) if isinstance(p.get("polarization"), list)
                        else str(p.get("polarization", "")),
                        "size_GB": round((p.get("bytes") or 0) / 1e9, 2), "file": name, "url": url})
    if new:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            for row in sorted(new, key=lambda r: r["start_utc"]):
                w.writerow(row)
    print(f"refresh: {len(new)} new NISAR files since {last}")
    return len(new)


# ---------------- 2. update products ----------------
def update():
    for script in ("nisar_pixel_stack.py", "nisar_pixel_products.py"):
        subprocess.run([PY, str(ROOT / "scripts" / "nisar" / script), "--track", str(TRACK)], check=True, cwd=ROOT)


# ---------------- 3. alerts ----------------
HOT_SHARE = 0.4                                  # share of a 100 m cell's forest pixels that must be weakening
GMW_SHARE = 0.05                                 # GMW loss 2015-2025 covering >= 5% of the patch and 200 m around it
L_PCT = 50                                       # ALOS-2 drop in >= 50% of the patch's forest pixels
MIN_HA_STEPS = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)   # smallest patch kept: the first step where shuffled data gives < 1 alert
SUPPORT = {                                      # supporting records, checked after the NISAR trend has flagged a patch
    "long_term_record": "long-term L-band record (Global Mangrove Watch / ALOS-2)",
    "optical_greenness": "optical greenness (Landsat)",
    "cband_radar": "C-band radar (Sentinel-1)",
    "nisar_structure": "NISAR structural change",
}


def components(mask):
    lab = np.zeros(mask.shape, int)
    n = 0
    for i, j in zip(*np.nonzero(mask)):
        if lab[i, j]:
            continue
        n += 1
        stack = [(i, j)]
        lab[i, j] = n
        while stack:
            a, b = stack.pop()
            for da in (-1, 0, 1):
                for db in (-1, 0, 1):
                    x, y = a + da, b + db
                    if 0 <= x < mask.shape[0] and 0 <= y < mask.shape[1] and mask[x, y] and not lab[x, y]:
                        lab[x, y] = n
                        stack.append((x, y))
    return lab, n


def cell_sum(a, c=CELL):
    H, W = a.shape[0] // c, a.shape[1] // c
    return a[:H * c, :W * c].reshape(H, c, W, c).sum((1, 3))


def window_sum(a, r):
    """Sum over a (2r+1) x (2r+1) window of cells."""
    p = np.pad(a.astype("float64"), r)
    return sum(p[i:i + a.shape[0], j:j + a.shape[1]] for i in range(2 * r + 1) for j in range(2 * r + 1))


def relative_drop(late_db, early_db, forest):
    """dB change between two images after a 3x3 speckle filter in linear power, minus the forest-wide median change
    (a whole mosaic can shift: the 2016 ALOS-2 mosaic is ~0.9 dB darker everywhere)."""
    f = lambda a: 10 * np.log10(box(10 ** (a / 10)))
    d = f(late_db) - f(early_db)
    return d - np.nanmedian(d[forest])


def ndvi_change(tr, crs, shape):
    """Landsat dry-season NDVI change 2015-16 -> 2024-25 on the NISAR grid. Read back from our own colourised
    export (white = 0, full colour = +-0.4), so it is exact to about 0.002. Works for the red-white-green and the
    red-white-blue version of that layer. Returns None if the export is not there."""
    path = EE / "l8_ndvi_change_2015_16_to_2024_25.tif"
    if not path.exists():
        return None
    with rasterio.open(path) as s:
        r, g, b, alpha = (s.read(i).astype("float32") for i in (1, 2, 3, 4))
        value = np.where(r >= 254.5, 0.4 * (np.minimum(g, b) / 255 - 1), 0.4 * (1 - r / 255))
        value[alpha < 255] = np.nan
        out = np.full(shape, np.nan, "float32")
        reproject(value, out, src_transform=s.transform, src_crs=s.crs, src_nodata=np.nan, dst_transform=tr,
                  dst_crs=crs, dst_nodata=np.nan, resampling=Resampling.average)
    return out


def alerts():
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    npx = stats["nisar_pixel"]
    with rasterio.open(NISAR / "nisar_hv_trend_2025_26_value.tif") as s:
        slope = s.read(1)
        tr, crs = s.transform, s.crs
    aux = np.load(NISAR / "trend_aux_2025_26.npz")
    with rasterio.open(NISAR / "nisar_change_type_2025_26_value.tif") as s:
        ctype = s.read(1)
    forest = np.isfinite(slope)
    weak = forest & (np.abs(aux["tstat"]) >= 2) & (slope <= npx["trend"]["weakening_threshold"])
    struct_loss = ctype == 1
    px_ha = abs(tr.a * tr.e) / 1e4

    # older records, on the same grid
    with rasterio.open(OLDER) as o:
        old = {o.descriptions[i]: o.read(i + 1) for i in range(o.count)}
    l_drop = relative_drop(old["alos_hv_2024"], old["alos_hv_2015"], forest) <= -2.0     # L-band (ALOS-2), 2015 -> 2024
    c_drop = relative_drop(old["s1_vh_2025_26"], old["s1_vh_2017_18"], forest) <= -2.0   # C-band (Sentinel-1), 2018 -> 2026
    dndvi = ndvi_change(tr, crs, slope.shape)
    g_drop = (dndvi <= -0.10) if dndvi is not None else np.zeros(slope.shape, bool)       # Landsat NDVI, 2016 -> 2025
    gmw_tif = [g for g in glob.glob(str(ROOT / "data_raw" / "gmw_v4" / "**" / "*N25E067*.tif"), recursive=True)
               if not Path(g).name.startswith("._")][0]
    with rasterio.open(gmw_tif) as g:
        lost15 = ((g.read(2015 - 1985 + 1) == 1) & (g.read(g.count) != 1)).astype("float32")
        gmw_loss = np.zeros(slope.shape, "float32")
        reproject(lost15, gmw_loss, src_transform=g.transform, src_crs=g.crs, dst_transform=tr, dst_crs=crs,
                  resampling=Resampling.average)
    gmw_loss = gmw_loss > 0.3                                         # GMW: mangrove in 2015, gone by 2025

    # zones (40-year GMW decline) rasterised on the NISAR grid
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    zones = json.loads(ZONES.read_text(encoding="utf-8"))["features"] if ZONES.exists() else []
    zone_id = np.zeros(slope.shape, "int16")
    for k, f in enumerate(zones, 1):
        g = stransform(sshape(f["geometry"]).buffer(0.002),   # ~200 m halo: the edge of a shrinking patch counts too
                       lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
        zone_id[rasterize([(g, 1)], out_shape=slope.shape, transform=tr, fill=0).astype(bool) & (zone_id == 0)] = k

    # everything per 100 m cell
    n_forest = cell_sum(forest.astype(int))
    n_weak = cell_sum(weak.astype(int))
    n_struct = cell_sum((struct_loss & forest).astype(int))
    n_ldrop = cell_sum((l_drop & forest).astype(int))
    n_cdrop = cell_sum((c_drop & forest).astype(int))
    n_gdrop = cell_sum((g_drop & forest).astype(int))
    n_gmw = cell_sum(gmw_loss.astype(int))
    n_zone = cell_sum((zone_id > 0).astype(int))
    forest_cell = n_forest >= 8
    H, W = n_forest.shape

    def support(cm):
        """The four supporting records for a group of cells (a patch, or one cell for the base rates)."""
        nf = max(float(n_forest[cm].sum()), 1)
        near = window_sum(cm, 2) > 0                                   # the cells plus 200 m around them
        gmw_ha = float(n_gmw[near].sum()) * px_ha
        near_ha = float(near.sum()) * CELL * CELL * px_ha
        v = {"zone_px": int(n_zone[cm].sum()), "gmw_ha": gmw_ha, "gmw_ratio": gmw_ha / near_ha,
             "l_pct": 100 * float(n_ldrop[cm].sum()) / nf, "g_pct": 100 * float(n_gdrop[cm].sum()) / nf,
             "c_pct": 100 * float(n_cdrop[cm].sum()) / nf, "struct_pct": 100 * float(n_struct[cm].sum()) / nf}
        v["signals"] = {
            # GMW v4.1 is partly built from JAXA L-band radar, the same family as ALOS-2: one record, not two
            "long_term_record": v["zone_px"] >= CELL * CELL or v["gmw_ratio"] >= GMW_SHARE or v["l_pct"] >= L_PCT,
            "optical_greenness": v["g_pct"] >= 25,
            "cband_radar": v["c_pct"] >= 25,
            "nisar_structure": v["struct_pct"] >= 10,
        }
        return v

    # base rates: how common is each record over ALL forest cells? A record a third of the forest meets is weak evidence
    gmw_near_ratio = window_sum(n_gmw, 2) / window_sum(np.full(n_gmw.shape, CELL * CELL), 2)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = lambda a: np.where(forest_cell, a / np.maximum(n_forest, 1), 0)
        cell_sig = {
            "long_term_record": (n_zone >= CELL * CELL) | (gmw_near_ratio >= GMW_SHARE) | (share(n_ldrop) >= L_PCT / 100),
            "optical_greenness": share(n_gdrop) >= 0.25,
            "cband_radar": share(n_cdrop) >= 0.25,
            "nisar_structure": share(n_struct) >= 0.10,
        }
    n_cells = max(int(forest_cell.sum()), 1)
    base_rates = {k: round(100 * float((m & forest_cell).sum()) / n_cells, 1) for k, m in cell_sig.items()}
    base_rates["two_or_more"] = round(100 * float(((sum(m.astype(int) for m in cell_sig.values()) >= 2) & forest_cell).sum()) / n_cells, 1)

    def patches(n_weak_cells):
        """Connected groups of 'hot' 100 m cells -> list of (cell mask, weakening hectares)."""
        hot = forest_cell & (n_weak_cells >= HOT_SHARE * n_forest)
        lab, n = components(hot)
        return [(lab == k, float(n_weak_cells[lab == k].sum()) * px_ha) for k in range(1, n + 1)]

    # how many alerts would noise alone raise? Same pipeline on the date-shuffled trend rasters
    fmask, n_f = aux["forest"], int(aux["n_forest"])
    null_ha = []
    for packed in aux["null_weak"]:
        w = np.zeros(slope.shape, bool)
        w[fmask] = np.unpackbits(packed)[:n_f].astype(bool)
        null_ha.append([ha for _, ha in patches(cell_sum(w.astype(int)))])
    expected = {step: float(np.mean([sum(h >= step for h in run) for run in null_ha])) for step in MIN_HA_STEPS}
    min_ha = next((step for step in MIN_HA_STEPS if expected[step] < 1), MIN_HA_STEPS[-1])

    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    last_date = npx["source"].split(" dates ")[1].split("-")[1][:8]
    last_pass = dt.date(int(last_date[:4]), int(last_date[4:6]), int(last_date[6:]))
    next_pass, overdue = last_pass + dt.timedelta(days=REPEAT_DAYS), []
    while next_pass <= dt.date.today():          # passes that have flown but are not in our stack yet
        overdue.append(next_pass.isoformat())
        next_pass += dt.timedelta(days=REPEAT_DAYS)
    r_tide = aux["r_tide"] if "r_tide" in aux.files else None

    cands = []
    for cm, ha in patches(n_weak):
        if ha < min_ha:
            continue
        cells = np.argwhere(cm)
        w = n_weak[cm].astype(float)             # weighted centre in pixel space
        ci = (cells[:, 0] * CELL + CELL / 2) @ w / w.sum()
        cj = (cells[:, 1] * CELL + CELL / 2) @ w / w.sum()
        x, y = tr * (cj, ci)
        lon, lat = to_ll.transform(x, y)
        pm = np.zeros(slope.shape, bool)         # the patch's pixels
        pm[:H * CELL, :W * CELL] = np.kron(cm, np.ones((CELL, CELL), bool))
        zp = zone_id[pm]
        zk = int(np.bincount(zp[zp > 0]).argmax()) if (zp > 0).sum() >= CELL * CELL else 0
        v = support(cm)
        cands.append(v | {"lon": lon, "lat": lat, "ha": ha, "zone": zones[zk - 1]["properties"] if zk else None,
                          "slope": float(np.nanmean(slope[pm & weak])), "support": sum(v["signals"].values()),
                          "r_tide": float(np.nanmedian(r_tide[pm & weak])) if r_tide is not None else None})
    histogram = {str(k): sum(c["support"] == k for c in cands) for k in range(len(SUPPORT) + 1)}
    cand_rates = {k: round(100 * sum(c["signals"][k] for c in cands) / max(len(cands), 1), 1) for k in SUPPORT}
    # which ones to show: the largest (the shuffle test shows noise does not make large patches); keep ~500 m apart.
    # Supporting records do not decide the order: candidates meet them about as often as the forest as a whole
    # (compare base_rates with pct_of_candidates_meeting_each_record in the feed).
    cands.sort(key=lambda c: -c["ha"])
    picked = []
    for c in cands:
        if all(abs(c["lon"] - p["lon"]) * 101000 + abs(c["lat"] - p["lat"]) * 110600 > 500 for p in picked):
            picked.append(c)
        if len(picked) == MAX_ALERTS:
            break

    feats, feed = [], []
    for i, c in enumerate(picked, 1):
        z, sig = c["zone"], c["signals"]
        # fixed rule, not position in the list: two or more supporting records = check first
        pr = "Check first" if c["support"] >= 2 else "Field check"
        observed = (f"{c['ha']:.1f} ha of mangrove here lost radar strength through 2025-26 "
                    f"({c['slope']:.1f} dB/yr vs the rest of the forest; a steady decline through the year).")
        lines = []
        if z:
            lines.append(f"Global Mangrove Watch: inside decline zone {z['id']}, which lost {z['lost_pct']:.0f}% of its "
                         f"mangrove since {z['peak_year']} ({z['peak_km2']:.2f} → {z['km2_2025']:.2f} km²).")
        elif c["gmw_ratio"] >= GMW_SHARE:
            lines.append(f"Global Mangrove Watch: {c['gmw_ha']:.1f} ha of mangrove within 200 m disappeared between 2015 and 2025.")
        if c["l_pct"] >= L_PCT:
            lines.append(f"Older L-band radar (ALOS-2): {c['l_pct']:.0f}% of this forest lost ≥2 dB more than the forest "
                         f"as a whole between 2015 and 2024.")
        if sig["optical_greenness"]:
            lines.append(f"Landsat greenness: {c['g_pct']:.0f}% of this forest is less green (NDVI down by 0.1 or more) "
                         f"than in 2015-16.")
        if sig["cband_radar"]:
            lines.append(f"Sentinel-1 C-band: {c['c_pct']:.0f}% of this forest lost ≥2 dB more than the forest as a whole "
                         f"since 2018.")
        if sig["nisar_structure"]:
            lines.append(f"NISAR change type: {c['struct_pct']:.0f}% of this forest shows a structural (canopy) drop, "
                         f"not just wetter or drier ground.")
        names = [SUPPORT[k] for k in SUPPORT if sig[k]]
        confidence = (f"NISAR trend plus {c['support']} of {len(SUPPORT)} supporting records"
                      + (f" ({'; '.join(names)})" if names else "") + ". Not field-checked.")
        title = f"Alert {i}: radar signal weakening" + (f" in decline zone {z['id']}" if z else "") + " (not field-checked)"
        maps = f"https://www.google.com/maps?q={c['lat']:.5f},{c['lon']:.5f}"
        props = {
            "kind": "alert",
            "priority": pr,
            "title": title,
            "observed": observed,
            "evidence": " ".join(lines) or "NISAR trend only; no older record of decline here.",
            "confidence": confidence,
            "possible_causes": "To verify on the ground: wood cutting, camel/livestock browsing, land filling or "
                               "construction, blocked tidal channels, sewage/industrial discharge, sediment burial. "
                               "It may also be tide or season rather than damage.",
            "next_step": f"Field visit with photos at {c['lat']:.5f} N, {c['lon']:.5f} E. "
                         f"NISAR's next pass is around {next_pass.isoformat()}.",
            "area_ha": round(c["ha"], 1),
            "zone": z["id"] if z else None,
            "maps_url": maps,
            "supporting_records": c["support"],
            "signals": sig,
        }
        if c["r_tide"] is not None:
            props["tide_check"] = (f"This patch's signal {'follows' if abs(c['r_tide']) >= 0.5 else 'does not follow'} the "
                                   f"predicted tide height at each pass (correlation {c['r_tide']:+.2f}).")
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [round(c["lon"], 5), round(c["lat"], 5)]}})
        feed.append(props | {"lon": round(c["lon"], 5), "lat": round(c["lat"], 5)})

    # keep non-alert places (restoration sites, stories) that the team added by hand
    old_places = json.loads(PLACES.read_text(encoding="utf-8")) if PLACES.exists() else {"features": []}
    keep = [f for f in old_places["features"] if f["properties"].get("kind") not in ("alert", "flag")]
    PLACES.write_text(json.dumps({"type": "FeatureCollection", "features": feats + keep}, indent=1, ensure_ascii=False)
                      + "\n", encoding="utf-8")
    n_runs = len(null_ha)
    meta = {
        "generated": dt.date.today().isoformat(), "last_nisar_pass": last_date, "next_nisar_pass": next_pass.isoformat(),
        "passes_not_yet_published": overdue, "track": TRACK,
        "method": f"Entry condition: 100 m cells where >= {HOT_SHARE:.0%} of the mangrove pixels (Global Mangrove Watch 2025) "
                  f"weaken by >= 1 dB/yr relative to the whole forest (|t| >= 2 per pixel, adjusted for autocorrelation, "
                  f"not corrected for season); touching cells are joined; patches >= {min_ha:g} ha. Each patch is then "
                  f"checked against {len(SUPPORT)} supporting records: long-term L-band record (GMW decline zone, or GMW "
                  f"loss 2015-2025 over >= {GMW_SHARE:.0%} of the patch and the 200 m around it, or ALOS-2 HV drop >= 2 dB "
                  f"2015-2024 relative to the forest in >= {L_PCT}% of the patch; GMW and ALOS-2 share JAXA L-band data, so they count "
                  f"once); Landsat NDVI drop >= 0.1 from 2015-16 to 2024-25 in >= 25%; Sentinel-1 VH drop >= 2 dB "
                  f"2018-2026 relative to the forest in >= 25%; NISAR structural canopy loss in >= 10%. 'Check first' = "
                  f"two or more supporting records. Shown: the {MAX_ALERTS} largest, at least 500 m apart.",
        "candidates": len(cands), "shown": len(feed),
        "candidates_by_supporting_records": histogram,
        "by_chance": {
            "method": f"The same alert pipeline on {n_runs} trend maps made with the order of the passes shuffled. "
                      f"Measures random noise only, not season or tide.",
            "min_patch_ha": min_ha,
            "expected_alerts": round(expected[min_ha], 2),
            "most_in_one_run": int(max(sum(h >= min_ha for h in run) for run in null_ha)),
            "expected_alerts_by_min_patch_ha": {str(k): round(v, 2) for k, v in expected.items()},
        },
        "base_rates_pct_of_forest_cells": base_rates | {
            "what": "Share of all 100 m forest cells that meet each supporting record on their own. The higher the "
                    "share, the weaker that record is as evidence."},
        "pct_of_candidates_meeting_each_record": cand_rates | {
            "what": "Compare with the base rates: a record that candidates meet no more often than the forest as a "
                    "whole does not single them out."},
        "supporting_records": SUPPORT,
        "alerts": feed,
    }
    ALERTS.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    BULLETIN.parent.mkdir(parents=True, exist_ok=True)
    md = ["# CoastLens mangrove alerts: Karachi coast", "",
          f"Latest NISAR pass: {last_pass.isoformat()} · next pass about {next_pass.isoformat()} · generated {meta['generated']}"
          + (f" · flown but not yet published: {', '.join(overdue)}" if overdue else ""), "",
          "These are places where the mangrove's NISAR radar signal weakened this year compared with the rest of the "
          "forest. They are leads for a field visit, not proof of damage: the cause can also be tide or season. "
          "Please send photos and notes back so we can confirm or clear each alert.", "",
          f"{len(feed)} of {len(cands)} candidate patches are listed. Random noise alone would be expected to raise about "
          f"{expected[min_ha]:.1f} patch(es) of this size.", ""]
    for p in feed:
        md += [f"## {p['title']} · {p['priority'].lower()}", "",
               f"- **Where:** {p['lat']} N, {p['lon']} E: [open in Google Maps]({p['maps_url']})",
               f"- **Size:** about {p['area_ha']} ha",
               f"- **What NISAR sees:** {p['observed']}",
               f"- **Older records:** {p['evidence']}",
               f"- **How much agrees:** {p['confidence']}"]
        if "tide_check" in p:
            md.append(f"- **Tide:** {p['tide_check']}")
        md += [f"- **Possible causes (to check):** {p['possible_causes']}", ""]
    BULLETIN.write_text("\n".join(md), encoding="utf-8")
    print(f"alerts: {len(feed)} of {len(cands)} candidates written; min patch {min_ha} ha; "
          f"{expected[min_ha]:.2f} expected by chance; next pass {next_pass}")
    print("by supporting records:", histogram, "| base rates:", base_rates, "| among candidates:", cand_rates, "| chance by min ha:", expected)
    for p in feed:
        print(f"  {p['priority']:12} {p['lat']},{p['lon']} {p['area_ha']} ha zone={p['zone']} {p['confidence']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--alerts", action="store_true", help="only rebuild alerts from existing products")
    args = ap.parse_args()
    if not args.alerts:
        refresh()
        update()
    alerts()


if __name__ == "__main__":
    main()
