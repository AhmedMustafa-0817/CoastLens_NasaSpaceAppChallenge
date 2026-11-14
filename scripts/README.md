# CoastLens data pipeline

The website only displays finished files. All processing happens here, ahead of time.

```
Earth Engine (export_layers.js) ──► <id>.tif (RGB+alpha) ─┐
                                                          ├─► make_tiles.py ─► public/tiles/<id>/{z}/{x}/{y}.png
ASF NISAR GCOV .h5 ─► nisar_gcov_to_geotiff.py ─► <id>_rgba.tif ─┘
Earth Engine STATS console output ───────────────────────────────► public/data/stats.json
```

## One-time setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r scripts/requirements.txt
```

No GDAL command-line install is needed. Everything uses `rasterio` wheels.

## Optical, mangrove and Sentinel-1 layers (Earth Engine)

1. Open https://code.earthengine.google.com, paste `scripts/ee/export_layers.js`, and click **Run**.
2. In the **Tasks** tab, click **RUN** on each export. The files land in Google Drive `coastlens_exports/`.
3. Copy the printed **STATS** JSON into `public/data/stats.json`.
4. Download each `.tif`, then tile it:
   ```bash
   python scripts/tiles/make_tiles.py l8_truecolor_2024_25.tif public/tiles/l8_truecolor_2024_25
   python scripts/tiles/make_tiles.py gmw_2020.tif public/tiles/gmw_2020 --categorical   # class maps
   ```
5. In `public/data/layers.json`, set that layer's `"status": "ready"`.

## NISAR (ASF Vertex)

1. At https://search.asf.alaska.edu, draw the AOI and filter to NISAR. Note the date, track/frame, direction and polarisations.
2. Download an **L2 GCOV** file (an Earthdata login is required).
3. Find the real dataset paths:
   ```bash
   python scripts/nisar/nisar_gcov_to_geotiff.py <file>.h5 --inspect
   ```
   The default paths in the script are our best reading of the product layout. **Check them against `--inspect` output and the official NISAR product spec.** Pass `--grid` / `--epsg` if they differ.
4. Convert and clip:
   ```bash
   python scripts/nisar/nisar_gcov_to_geotiff.py <file>.h5 --pol HVHV --bbox 67.214098 24.796252 67.251778 24.821254 --out nisar_hv_YYYYMMDD
   python scripts/tiles/make_tiles.py nisar_hv_YYYYMMDD_rgba.tif public/tiles/nisar_hv_YYYYMMDD
   ```
5. Add a layer entry to `layers.json` with `"id": "nisar_hv_YYYYMMDD"`, the real date, product and polarisation, and `"status": "ready"`. Remove `nisar_placeholder` once a real NISAR layer exists.
6. Keep `nisar_hv_YYYYMMDD_db.tif` (real dB values) for statistics. The `_rgba.tif` is for display only.

## NISAR without downloading whole files

Every NISAR script accepts an `https://` URL from `docs/nisar_scenes_rehri_goth.csv` and reads **only our area** over HTTP (`scripts/nisar/remote_h5.py`). It needs the Earthdata token saved once:

```bash
python scripts/nisar/earthdata_auth.py --save      # paste token (hidden), stored in Windows Credential Manager
```

| What | Command |
|---|---|
| Backscatter layer (GCOV) | `python scripts/nisar/nisar_gcov_to_geotiff.py <GCOV url> --pol HVHV --looks 2 --bbox 67.214098 24.796252 67.251778 24.821254 --out data_raw/nisar/nisar_hv_YYYYMMDD` |
| Coherence layer (GUNW) | `python scripts/nisar/nisar_gcov_to_geotiff.py <GUNW url> --grid science/LSAR/GUNW/grids/frequencyA/wrappedInterferogram --pol HH/coherenceMagnitude --epsg 32642 --linear --vmin 0 --vmax 1 --bbox 67.214098 24.796252 67.251778 24.821254 --out data_raw/nisar/nisar_coh_D1_D2` |
| Zone stats + HV change map | `python scripts/nisar/nisar_stats_and_change.py --scene … --change EARLY_db.tif LATE_db.tif --change-out …` |
| Year-long time series (full res; `--freq B` = 80 m for big areas) | `python scripts/nisar/nisar_timeseries.py --track 164` → `stats.json › nisar_timeseries` |

**Product versions:** never mix a BETA file with a later one. BETA GCOV files read several dB darker than the PROVISIONAL/V1 reprocessing of the same date. The before/after HV layers therefore use **track 164** (21 Nov 2025 and 11 Oct 2026, both PROVISIONAL, same quad-pol 20 m mode), not track 142, which is BETA-only for Nov 2025 – Jan 2026.

**Same-season comparison:** when NISAR publishes Nov 2026 scenes on track 164 (check the ASF search), run the GCOV command for that date and `nisar_stats_and_change.py --change` against `nisar_hv_20251121_db.tif`. Use the same imaging mode (`2005_QPDH`) so the grids match.

## Study area and investigation flags

- **Study area: Karachi mangrove coast, Rehri Goth to Port Qasim**, box `67.155304, 24.671376, 67.433395, 24.828817` (about 28 × 17.5 km, ~490 km²). `public/data/aoi.geojson` holds the same box as a polygon. Earlier boxes are archived locally: `data_raw/rehri_small_box/` (3.8 × 2.8 km Rehri Goth box) and `data_raw/keti_bandar/`.
- Water mask for the zone statistics: `water_s2_2025_26` (Sentinel-2 MNDWI > 0), exported by `export_layers.py` and not shown on the site.
- Map pins (`public/data/places.geojson`) are now written by the **monitor** (below). Hand-added restoration sites and stories in that file are kept.

## NISAR-only products (per pixel)

```bash
python scripts/nisar/nisar_pixel_stack.py --track 164      # every GCOV date → data_raw/nisar/stack_164/*.npz (common 20 m grid)
python scripts/nisar/nisar_pixel_products.py --track 164   # → AI map, land cover, forest watch, change type, single passes + stats.json › nisar_pixel
python scripts/tiles/make_tiles.py data_raw/nisar/<id>_rgba.tif public/tiles/<id> --zoom 10-14 --clip 67.155304 24.671376 67.433395 24.828817   # add --categorical for class maps; Sentinel-2: 10-15
```

- **Imaging modes:** track 164 alternates quad-pol (`2005_QPDH`, 20 m) and dual-pol (`4005_DHDH`, 10 m) passes. On the same 20 m grid a dual-pol pass reads differently from its quad-pol neighbours, and by a different amount on each surface (`stats.json › nisar_pixel.mode_offset`), so there is no single correction. Yearly means, the AI features, the land-cover rules and the structural-vs-moisture windows use **quad-pol passes only**. The HV trend uses every pass with the mode as a covariate.
- **AI mangrove map (`nisar_ai_mangrove_2025_26`):** Random Forest on 10 NISAR-only features, trained on GMW v4.1 2025 labels, validated on 2 km checkerboard blocks it never saw, on pixels GMW is sure about. Accuracy, precision, recall, F1 and the confusion matrix are in `stats.json › nisar_pixel.ai.held_out_accuracy`. The published map is a second model trained on the whole box. Needs `scikit-learn`.
- **Land-cover map from simple rules (`nisar_classes_2025_26`):** thresholds on year-mean HV, HH, HV−HH and 100 m HV texture, set by eye on the Rehri Goth sub-area (about 2% of the box) and not re-tuned against GMW; agreement is measured over the whole box.
- **Structural vs moisture change (`nisar_change_type_2025_26`):** Nov–Dec 2025 vs Aug–Oct 2026, three quad-pol passes each, averaged and smoothed in linear power. Both polarisations moving together = moisture/flooding; HV moving much more than HH = canopy (structure) change.
- Also writes the single-pass HV/HH layers (HH on its own −20 to 0 dB grey scale), the HV change layer, `stats.json › nisar` and NISAR's status inside each decline zone.
- **Forest watch:** each mangrove pixel's HV slope, *relative to the forest median on every date*. Only shifts common to the whole forest cancel (such as calibration); a patch whose seasonal or tidal response differs from the forest's still gets a slope. The forest mask is GMW 2025, not the AI map (which is built from the same year of data). Pixels with |t| < 2 (adjusted for autocorrelation) are faded.
- **How much is noise:** the script refits the trend 20 times with the order of the passes shuffled and writes the flagged share to `stats.json › nisar_pixel.trend.by_chance`. The shuffled flags go to `data_raw/nisar/trend_aux_2025_26.npz`, which the monitor uses to count alerts expected by chance.
- **Tide:** `python scripts/nisar/tide_at_pass.py` writes `docs/tide_at_pass.csv` (predicted tide height at each pass, GOT4.10 model via `pyTMD`). If the file is there, tide becomes a covariate in the trend and the correlations are written to `stats.json › nisar_pixel.trend.tide`.
- With one year of data this ranks patches against each other; it is not yet a multi-year trend. A same-season comparison (Nov–Dec 2025 vs Nov–Dec 2026, quad-pol) is the next step once those passes are published.
- **Colours:** every change layer uses red for a decrease and blue for an increase. Green is kept for vegetation classes.
- **Numbers in the layer text:** write them in `layers.json` as `{{path.in.stats.json}}`; the map page fills them in, so text and statistics cannot drift apart.

## Older satellites on the NISAR grid (comparison + long-term evidence)

```bash
python scripts/ee/older_sensors.py    # data_raw/ee/older_on_nisar_grid.tif + stats.json › zone_history
```

- **Grid:** Landsat NDVI, Sentinel-1 VH and ALOS-2 HV (2015, 2024) resampled onto the exact NISAR 20 m grid, so every sensor is compared on the same pixels (`stats.json › nisar_pixel.sensor_comparison`, AUC per sensor).
- **History:** yearly Landsat NDVI (1989–2026), ALOS L-band HV (2007–2024) and Sentinel-1 VH (2016–2026) inside every decline zone and a stable reference forest.

## NGO monitor (runs after every NISAR pass)

```bash
python scripts/monitor/coastlens_monitor.py            # refresh scene list (asf_search) → update NISAR stack + products → alerts
python scripts/monitor/coastlens_monitor.py --alerts   # only re-rank alerts from existing products
```

Writes `public/data/places.geojson` (alert pins), `public/data/alerts.json` (feed) and `docs/alerts/latest.md` (bulletin for NGOs). **Entry condition:** a patch of 100 m cells where ≥ 40% of the mangrove pixels weaken by ≥ 1 dB/yr relative to the whole forest (|t| ≥ 2). The smallest patch kept is set from the date-shuffled trend maps so that noise alone raises fewer than one alert. Each patch is then checked against four **supporting records**: the long-term L-band record (GMW decline zone, GMW loss 2015–2025 nearby, or an ALOS-2 drop; GMW is partly built from JAXA L-band radar, so these count once), Landsat NDVI drop, Sentinel-1 drop, and NISAR structural change. The feed publishes the number of candidates, how many random noise would raise, and how common each supporting record is across the whole forest (a record that half the forest meets is weak evidence). The eight largest candidates are shown. An alert says "the radar signal weakened here", never "thinning": alerts are leads for field visits, never proof.

## Global Mangrove Watch v4.1 (1985–2025)

Download only tile `N25E067` from the 41-band stack at https://zenodo.org/records/21346457 (`gmw_mng_ext_v4112_stack.tar.gz`, stream it through `tar -xz --wildcards '*N25E067*'`), then:

```bash
python scripts/analysis/gmw_timeseries.py data_raw/gmw_v4/gmw_mng_ext_v4112_stack/GMW_N25E067_v4112_mng_ext.tif   # stats.json › gmw_timeseries + CSV
python scripts/analysis/gmw_v4_layers.py  data_raw/gmw_v4/gmw_mng_ext_v4112_stack/GMW_N25E067_v4112_mng_ext.tif   # gmw4_1985, gmw4_2025, gmw4_change_1985_2025
python scripts/analysis/gmw_decline_zones.py data_raw/gmw_v4/gmw_mng_ext_v4112_stack/GMW_N25E067_v4112_mng_ext.tif # zones.geojson, stats › decline_zones, gmw4_lossyear
```

**Decline zones:** ~250 m cells whose mangrove, after a peak year ≤ 2018, lost ≥ 40% and kept falling (Kendall tau ≤ −0.5) without recovering; touching cells are joined and zones that lost < 0.1 km² are dropped.

The box's yearly areas match the GMW website's custom-area widget within ~1%.

## Rules

- A layer is `"ready"` only if its tiles come from real data. Never ship mock layers as real.
- Layer `id` = export name = tiles folder name.
- Keep `legend` in `layers.json` in sync with `STYLE` in `export_layers.js` (or with `--vmin/--vmax` for NISAR).
