"""CoastLens monitor: watches the mangroves with every new NISAR pass and tells NGOs where to go.

NISAR passes over Karachi every 12 days (track 164). Each run:
  1. refresh   ask ASF (asf_search) for new NISAR GCOV/GUNW files over the box and add them to
               docs/nisar_scenes_rehri_goth.csv
  2. update    read the new passes (nisar_pixel_stack.py) and rebuild the NISAR products
               (nisar_pixel_products.py: AI mangrove map, forest watch, structural vs moisture change)
  3. alerts    find patches of mangrove that NISAR sees thinning *now*, rank them by how much evidence
               agrees (40 years of GMW decline + NISAR trend + structural change), and write
                 public/data/places.geojson   alert pins on the map
                 public/data/alerts.json      machine-readable feed (for an app, SMS or e-mail bot)
                 docs/alerts/latest.md             a plain-language bulletin an NGO can read or forward

    python scripts/monitor/coastlens_monitor.py              # all three steps
    python scripts/monitor/coastlens_monitor.py --alerts     # only re-rank alerts from existing products

The "AI" is the Random Forest in nisar_pixel_products.py (learns mangrove from radar) plus the statistical
trend test here. Alerts are leads for a field visit, never proof of damage: every alert says so.
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

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable
CSV_PATH = ROOT / "docs" / "nisar_scenes_rehri_goth.csv"
NISAR = ROOT / "data_raw" / "nisar"
DATA = ROOT / "public" / "data"
STATS = DATA / "stats.json"
ZONES = DATA / "zones.geojson"
PLACES = DATA / "places.geojson"
ALERTS = DATA / "alerts.json"
OLDER = ROOT / "data_raw" / "ee" / "older_on_nisar_grid.tif"
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


def alerts():
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    npx = stats["nisar_pixel"]
    with rasterio.open(NISAR / "nisar_hv_trend_2025_26_value.tif") as s:
        slope = s.read(1)
        tr, crs = s.transform, s.crs
    with rasterio.open(NISAR / "nisar_hv_trend_2025_26_rgba.tif") as s:
        signif = s.read(4) == 255
    with rasterio.open(NISAR / "nisar_change_type_2025_26_value.tif") as s:
        ctype = s.read(1)
    forest = np.isfinite(slope)
    weak = forest & signif & (slope <= npx["trend"]["weakening_threshold"])
    struct_loss = ctype == 1

    # long-term evidence from the older satellites, on the same grid
    with rasterio.open(OLDER) as o:
        old = {o.descriptions[i]: o.read(i + 1) for i in range(o.count)}
    l_drop = (old["alos_hv_2024"] - old["alos_hv_2015"]) <= -2.0      # L-band (ALOS) lost >= 2 dB, 2015 -> 2024
    c_drop = (old["s1_vh_2025_26"] - old["s1_vh_2017_18"]) <= -2.0    # C-band (Sentinel-1) lost >= 2 dB, 2018 -> 2026
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
        g = stransform(sshape(f["geometry"]).buffer(0.002),   # ~200 m halo: edges of a dying patch count too
                       lambda xy: np.column_stack(to_utm.transform(xy[:, 0], xy[:, 1])))
        zone_id[rasterize([(g, 1)], out_shape=slope.shape, transform=tr, fill=0).astype(bool) & (zone_id == 0)] = k

    # 100 m cells where a large share of the forest is weakening
    n_forest = cell_sum(forest.astype(int))
    n_weak = cell_sum(weak.astype(int))
    n_struct = cell_sum((struct_loss & forest).astype(int))
    n_ldrop = cell_sum((l_drop & forest).astype(int))
    n_cdrop = cell_sum((c_drop & forest).astype(int))
    hot = (n_forest >= 8) & (n_weak >= 0.4 * n_forest)
    lab, n = components(hot)
    to_ll = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    px_ha = abs(tr.a * tr.e) / 1e4
    last_date = npx["source"].split(" dates ")[1].split("-")[1][:8]
    next_pass = (dt.date(int(last_date[:4]), int(last_date[4:6]), int(last_date[6:])) + dt.timedelta(days=REPEAT_DAYS))
    while next_pass <= dt.date.today():          # the next pass that has not happened yet
        next_pass += dt.timedelta(days=REPEAT_DAYS)

    cands = []
    for k in range(1, n + 1):
        cells = np.argwhere(lab == k)
        weak_px = int(n_weak[lab == k].sum())
        if weak_px * px_ha < 0.5:          # ignore < 0.5 ha (speckle-sized)
            continue
        # weighted centre in pixel space
        w = n_weak[lab == k].astype(float)
        ci = (cells[:, 0] * CELL + CELL / 2) @ w / w.sum()
        cj = (cells[:, 1] * CELL + CELL / 2) @ w / w.sum()
        x, y = tr * (cj, ci)
        lon, lat = to_ll.transform(x, y)
        r0, c0 = cells.min(0) * CELL
        r1, c1 = (cells.max(0) + 1) * CELL
        zid_patch = zone_id[r0:r1, c0:c1]
        zk = int(np.bincount(zid_patch[zid_patch > 0]).argmax()) if (zid_patch > 0).any() else 0
        nf_k = max(float(n_forest[lab == k].sum()), 1)
        struct_share = float(n_struct[lab == k].sum()) / nf_k
        l_share = float(n_ldrop[lab == k].sum()) / nf_k
        c_share = float(n_cdrop[lab == k].sum()) / nf_k
        # GMW recent loss within ~200 m of the patch
        h0, w0 = max(r0 - 10, 0), max(c0 - 10, 0)
        gmw_ha = float(gmw_loss[h0:r1 + 10, w0:c1 + 10].sum()) * px_ha
        mean_slope = float(np.nanmean(np.where(weak[r0:r1, c0:c1], slope[r0:r1, c0:c1], np.nan)))
        signals = {
            "nisar_now": True,
            "gmw_history": bool(zk) or gmw_ha >= 0.5,
            "lband_longterm": l_share >= 0.25,
            "cband_or_structure": c_share >= 0.25 or struct_share >= 0.10,
        }
        cands.append({"lon": lon, "lat": lat, "ha": weak_px * px_ha, "zone": zones[zk - 1]["properties"] if zk else None,
                      "struct_pct": 100 * struct_share, "l_pct": 100 * l_share, "c_pct": 100 * c_share,
                      "gmw_ha": gmw_ha, "slope": mean_slope, "signals": signals, "evidence": sum(signals.values())})
    # rank: evidence first, then size; keep ~500 m apart
    cands.sort(key=lambda c: (-c["evidence"], -c["ha"]))
    picked = []
    for c in cands:
        if all(abs(c["lon"] - p["lon"]) * 101000 + abs(c["lat"] - p["lat"]) * 110600 > 500 for p in picked):
            picked.append(c)
        if len(picked) == MAX_ALERTS:
            break

    priority = {4: "High", 3: "High", 2: "Medium", 1: "Watch"}
    feats, feed = [], []
    for i, c in enumerate(picked, 1):
        z = c["zone"]
        pr = priority[c["evidence"]]
        lines = [f"{c['ha']:.1f} ha of mangrove here lost radar strength through 2025-26 "
                 f"({c['slope']:.1f} dB/yr vs the rest of the forest, statistically significant)."]
        if z:
            lines.append(f"Global Mangrove Watch: inside decline zone {z['id']}, which lost {z['lost_pct']:.0f}% of its "
                         f"mangrove since {z['peak_year']} ({z['peak_km2']:.2f} → {z['km2_2025']:.2f} km²).")
        elif c["gmw_ha"] >= 0.5:
            lines.append(f"Global Mangrove Watch: {c['gmw_ha']:.1f} ha of mangrove right next to it disappeared between 2015 and 2025.")
        if c["signals"]["lband_longterm"]:
            lines.append(f"Older L-band radar (ALOS-2): {c['l_pct']:.0f}% of this forest already lost ≥2 dB between 2015 and 2024.")
        if c["c_pct"] >= 25:
            lines.append(f"Sentinel-1 C-band: {c['c_pct']:.0f}% of this forest lost ≥2 dB since 2018.")
        if c["struct_pct"] >= 10:
            lines.append(f"NISAR change type: {c['struct_pct']:.0f}% of this forest shows a structural (canopy) drop, "
                         f"not just wetter or drier ground.")
        title = (f"Alert {i}: mangrove thinning in decline zone {z['id']}" if z else f"Alert {i}: mangrove thinning")
        maps = f"https://www.google.com/maps?q={c['lat']:.5f},{c['lon']:.5f}"
        props = {
            "kind": "alert",
            "priority": pr,
            "title": title,
            "observed": lines[0],
            "evidence": " ".join(lines[1:]) or "NISAR trend only; no long-term decline recorded here yet (early warning).",
            "confidence": f"{pr} ({c['evidence']} of 4 independent signals agree). Not field-checked.",
            "possible_causes": "To verify on the ground: wood cutting, camel/livestock browsing, land filling or "
                               "construction, blocked tidal channels, sewage/industrial discharge, sediment burial.",
            "next_step": f"Field visit with photos at {c['lat']:.5f} N, {c['lon']:.5f} E. "
                         f"NISAR checks again around {next_pass.isoformat()}.",
            "area_ha": round(c["ha"], 1),
            "zone": z["id"] if z else None,
            "maps_url": maps,
            "signals": c["signals"],
        }
        feats.append({"type": "Feature", "properties": props,
                      "geometry": {"type": "Point", "coordinates": [round(c["lon"], 5), round(c["lat"], 5)]}})
        feed.append(props | {"lon": round(c["lon"], 5), "lat": round(c["lat"], 5)})

    # keep non-alert places (restoration sites, stories) that the team added by hand
    old = json.loads(PLACES.read_text(encoding="utf-8")) if PLACES.exists() else {"features": []}
    keep = [f for f in old["features"] if f["properties"].get("kind") not in ("alert", "flag")]
    PLACES.write_text(json.dumps({"type": "FeatureCollection", "features": feats + keep}, indent=1, ensure_ascii=False)
                      + "\n", encoding="utf-8")
    meta = {"generated": dt.date.today().isoformat(), "last_nisar_pass": last_date, "next_nisar_pass": next_pass.isoformat(),
            "track": TRACK, "method": "100 m cells where >= 40% of NISAR mangrove pixels weaken by >= 1 dB/yr relative "
            "to the whole forest (|t| >= 2); patches >= 0.5 ha; ranked by how many of 4 independent signals agree "
            "(NISAR trend now; GMW decline zone or GMW loss 2015-2025 within 200 m; ALOS-2 L-band HV drop >= 2 dB "
            "2015-2024 in >= 25% of the patch; Sentinel-1 VH drop >= 2 dB 2018-2026 in >= 25% or NISAR structural "
            "change in >= 10%), then by size.", "alerts": feed}
    ALERTS.write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    BULLETIN.parent.mkdir(parents=True, exist_ok=True)
    md = [f"# CoastLens mangrove alerts: Karachi coast", "",
          f"Latest NISAR pass: {last_date[:4]}-{last_date[4:6]}-{last_date[6:]} · next pass about {next_pass.isoformat()} · "
          f"generated {meta['generated']}", "",
          "These are places where the NISAR radar satellite sees mangrove thinning. They are leads for a field visit, "
          "not proof of damage. Please send photos and notes back so we can confirm or clear each alert.", ""]
    for p in feed:
        md += [f"## {p['title']} ({p['priority']} priority)", "",
               f"- **Where:** {p['lat']} N, {p['lon']} E: [open in Google Maps]({p['maps_url']})",
               f"- **Size:** about {p['area_ha']} ha",
               f"- **What NISAR sees:** {p['observed']}",
               f"- **Supporting evidence:** {p['evidence']}",
               f"- **Possible causes (to check):** {p['possible_causes']}", ""]
    BULLETIN.write_text("\n".join(md), encoding="utf-8")
    print(f"alerts: {len(feed)} written ({sum(p['priority'] == 'High' for p in feed)} high); next pass {next_pass}")
    for p in feed:
        print(f"  {p['priority']:6} {p['lat']},{p['lon']} {p['area_ha']} ha zone={p['zone']}")


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
