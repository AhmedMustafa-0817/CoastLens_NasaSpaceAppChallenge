# Sources for every figure on the site

## Our data (public/data/stats.json, written by scripts/, box 67.155304–67.433395°E, 24.671376–24.828817°N)
| On-screen figure | Value | Source |
|---|---|---|
| Mapped mangrove area 1985 / 1995 / 2005 / 2015 / 2025 | 67.2 / 80.7 / 119.4 / 168.4 / 180.9 km² | Global Mangrove Watch v4.1 (Zenodo 21346457), area computed by CoastLens (`scripts/analysis/gmw_timeseries.py`) |
| "+169%" | derived: (180.9 − 67.2) / 67.2 | computed in page |
| Decline zones (7), "−63% to −83%", zone A 0.78 km² (2008) → 0.16 km² (2025), "−80%" (home) | see `decline_zones` in stats.json and `zones.geojson` | GMW v4.1, `scripts/analysis/gmw_decline_zones.py` |
| Older GMW v3 vs v4.1 for 1996 | 184.1 vs 83.6 km² | GMW v3 (Earth Engine) and v4.1 |
| NDVI inside mangroves | 0.479, 0.494, 0.558, 0.513 | Landsat 8 C2 L2, Nov–Feb medians, inside GMW v3 2020 extent |
| Sentinel-1 VH | −14.88, −15.23 dB | Sentinel-1 GRD, Nov–Feb medians |
| NISAR echo bars (NISAR page) | water −21.98, town and land −13.16, mangrove −13.57 dB | NISAR L2 GCOV, track 164, pass of 2026-10-23, 80 m |
| NISAR passes | 28 passes listed, 27 used (14 Apr 2026 removed by quality check), 2025-11-21 to 2026-10-23: 26 provisional, 1 validated (23 Oct 2026); 17 quad-pol, 10 dual-pol | NISAR track 164, `stats.json › nisar_pixel.passes` |
| Coherence ranges | computed in page from the coherence series | NISAR L2 GUNW, track 164, 80 m |
| Eight NISAR alerts | see `alerts.json` (candidates, expected by chance, base rates) | `scripts/monitor/coastlens_monitor.py` (NISAR trend as entry condition; GMW/ALOS-2, Landsat NDVI, Sentinel-1 and NISAR structure as supporting records) |
| Tide height at each pass | `docs/tide_at_pass.csv` | GOT4.10 global ocean tide model (NASA GSFC) via pyTMD, `scripts/nisar/tide_at_pass.py` |
| AI mangrove map accuracy | see `stats.json › nisar_pixel.ai.held_out_accuracy` (accuracy, precision, recall, F1, confusion matrix), on 2 km blocks never used for training, pixels GMW is sure about | `scripts/nisar/nisar_pixel_products.py` |

## Outside figures (not our measurements)
| Figure | Source | Status |
|---|---|---|
| Global mangrove area 152,604 → 147,359 km² (−3.4%), 1996–2020 | Bunting et al. 2022, Global Mangrove Watch v3 | Check against the paper before final submission |
| Indus Delta 50,973 ha (1990) → 101,446 ha (2023) | Ahmed et al. 2025, Ecological Indicators, "Substantial rehabilitation of mangrove forests along the Indus Delta coastline of Pakistan: A 33-year review" | Taken from the abstract. Read the paper. Also cited on the map (GMW 1985 → 2025 layer and story 04) for planting in the wider Indus Delta; the map says the planted share of the gain in our box is not measured |
| Kharo Chan: 28 of 42 dehs lost to the sea | The News on Sunday, "The sea has grown closer" | News report. Find the primary source or soften the line |
| NISAR launch 30 Jul 2025, 747 km orbit, 12 m antenna, 12-day repeat, L-band ≈ 24 cm, S-band ≈ 9 cm | NASA / ISRO mission pages | Check against science.nasa.gov/mission/nisar |

## Statements without a number that still need a citation
- Mangroves as nursery habitat, wave buffer and carbon store (home page). Add a reference (for example IUCN or FAO) on the About page.
- The four mangrove facts on the 3D tree (pencil roots, salt on leaves, seedlings, nursery) describe the grey mangrove, *Avicennia marina*. Have a botanist or NGO contact confirm.

## Illustrations (not data)
Clouds, the 3D tree, the radar wave animations, the orbit drawing, and the S-band view.
