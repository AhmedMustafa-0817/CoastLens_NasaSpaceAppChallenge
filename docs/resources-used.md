# Challenge resources: what we used and why

Every link from the challenge page's **Resources** tab and the **Challenge Guide PDF** (bibliography), with what CoastLens does with it. "Used in" points to the script or page where it shows up.

## Data we actually process

| Resource | What we used it for | Purpose in the story | Used in |
|---|---|---|---|
| **ASF DAAC / ASF Vertex** (asf.alaska.edu, search.asf.alaska.edu) | Found and streamed every NISAR file over the box: 28 GCOV passes listed on track 164, 27 used (14 Apr 2026 removed by quality check) (Nov 2025 – Oct 2026) and GUNW coherence pairs on track 142. Only the box is read over HTTP (~20–45 MB per pass instead of 5 GB). | The core data: NISAR L-band HH and HV every 12 days. | `scripts/nisar/*`, `docs/nisar_scenes_rehri_goth.csv` |
| **asf_search** (Python module) | The monitor asks ASF for new NISAR passes over the box after every 12-day cycle and adds them to the scene list. | Makes the NGO alert system run on its own: new pass → new products → new alerts. | `scripts/monitor/coastlens_monitor.py` (`refresh`) |
| **NASA Earthdata Search / Earthdata login** (search.earthdata.nasa.gov, urs.earthdata.nasa.gov) | Product discovery (NISAR short names, versions BETA / PROVISIONAL / V1) and the login token that authorises the downloads (stored in Windows Credential Manager, never in code). | Access to NISAR; picking product versions that can be compared (BETA files read about 3–5 dB darker, most in mangrove). | `scripts/nisar/earthdata_auth.py` |
| **NISAR Science Users' Handbook / NISAR Data User Guide** (nisar-docs.asf.alaska.edu) | HDF5 layout of GCOV and GUNW (`science/LSAR/GCOV/grids/frequencyA/HVHV`, coherence paths), product levels, polarisation modes (quad-pol 20 m vs dual-pol 10 m). | Reading the files correctly, and lining up the 10 m and 20 m modes on one 20 m grid. | `nisar_gcov_to_geotiff.py`, `nisar_pixel_stack.py` |
| **Copernicus Data Space – Sentinel-1** (dataspace.copernicus.eu; we read the same archive through Google Earth Engine) | C-band VH backscatter 2015–2026: yearly history inside each decline zone, and a pixel-for-pixel comparison with NISAR. | "C-band vs L-band" (PDF key question 2): C-band bounces off the canopy top; it separates mangrove less well than NISAR's AI model (AUC 0.918 vs 0.992). | `scripts/ee/older_sensors.py`, Insights page |
| **Landsat / Sentinel-2** (optical, named in the challenge objectives) | True colour and NDVI layers; Landsat NDVI 1989–2026 inside each decline zone; Sentinel-2 water mask. | Context and the "optical vs radar" comparison: in decline zone C, L-band radar dropped against stable forest from 2017 and optical greenness in the 2018 dry season, about a year later at most. | `scripts/ee/export_layers.py`, `older_sensors.py` |
| **GDAL** (gdal.org) | Every raster step: we use `rasterio`, which is built on GDAL (reprojection onto the NISAR grid, clipping, GeoTIFF writing). | Turning HDF5 into GeoTIFFs and then web tiles (PDF key question 5). | all scripts, `scripts/tiles/make_tiles.py` |

## Knowledge and methods (not data)

| Resource | What we took from it | Where it shows |
|---|---|---|
| **NASA JPL NISAR mission portal** (nisar.jpl.nasa.gov) | Mission facts quoted on the site: L-band 24 cm, 12-day repeat, day/night, through cloud. | Landing page, layer descriptions |
| **ESA eoPortal NISAR profile** (eoportal.org) | Orbit and swath details (242 km swath, 12-day repeat) used to schedule the monitor's "next pass" date. | `coastlens_monitor.py` (`REPEAT_DAYS = 12`) |
| **ISRO NISAR page** (isro.gov.in) | S-band (9.3 cm) is ISRO's payload. ASF lists only L-band NISAR files over our box; S-band is distributed by ISRO and we did not obtain any for Karachi, so we use L-band only and say so. TODO: check ISRO's Bhoonidhi portal. | Future outlook |
| **Intro to Remote Sensing / Intro to SAR (Earthdata)** | Why HV measures woody volume and HH responds to double-bounce and water (PDF key question 1). | Layer explanations; the AI model's features |
| **NASA ARSET SAR / mangrove trainings** | Standard practice we follow: speckle filtering before analysis, multi-date averages, and mangrove mapping from cross-pol backscatter. | 3×3 speckle filter and year-mean features in `nisar_pixel_products.py` |
| **NASA ARIA** (aria.jpl.nasa.gov) | Inspiration from its damage-proxy maps: use radar change plus coherence to flag places worth checking, and label them as proxies, not confirmed damage. | The **structural vs moisture change** map (PDF key question 3), coherence layers |
| **NISAR Applications white papers** (Coastal Land Loss, Forest Resources, Forest Disturbance) | The "why it matters" framing and the future-outlook list: NISAR as a routine coastal forest-disturbance monitor. | Landing page story, NGO alerts, future outlook |
| **NISAR StoryMaps** | Format: one place, one question, map + charts + plain language. | Site structure (Landing → Map → Compare → Insights → Action) |
| **UAVSAR postcards** | Colour conventions for explaining L-band (green = forest/mangrove). | Map colours and legends |
| **CSA SAR Python tutorial** | Reading and calibrating SAR in Python without commercial software (PDF "data processing" bottleneck). | Our pure-Python pipeline (no GDAL install, no commercial tools) |

## Listed but not usable for Karachi (and why)

| Resource | Why not |
|---|---|
| **CSA RADARSAT Constellation Mission (RCM)** | Open products are mostly over Canada; no free coverage of Karachi. |
| **CSA RADARSAT-1 (1995–2013)** | Open archive is sparse outside Canada; Sentinel-1 and ALOS cover the same role here. |
| **CONAE SAOCOM (L-band)** | Downloads need a signed agreement and licence; not possible during the hackathon. We use JAXA ALOS/ALOS-2 L-band instead as the "before NISAR" L-band record. |

## Extra datasets we added (not in the list)

| Dataset | Why |
|---|---|
| **Global Mangrove Watch v4.1** (Zenodo 21346457), 1985–2025 yearly | 40-year mangrove history, decline zones, labels to train and test the AI model. |
| **JAXA ALOS / ALOS-2 PALSAR yearly mosaics** (2007–2010, 2015–2024) | The older L-band record before NISAR: in decline zone C its signal dropped up to about a year before optical greenness did, and how NISAR compares with its predecessor. |
| **GMW v3** (1996, 2007, 2010, 2020) | Kept only to show that older-satellite maps disagree with each other (v3 says 184 km² in 1996, v4.1 says 84 km²). |
