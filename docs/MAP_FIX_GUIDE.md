# CoastLens map: fix guide

Companion to `CoastLens_Map_Problems.pdf`, which shows each problem with screenshots. This file explains how to fix each one. Problem numbers (P1 to P21) are the same in both.

## Read this first

**What this is for.** The CoastLens map page was reviewed on 15 Nov 2026 in two ways: the live page was read layer by layer, and a read-only code audit was run on the repository at commit `f8f5ce8`. The analysis is solid. Most problems are wording that claims more than the analysis supports, plus a few method issues that need the raw data to fix.

**How to use it.** Read it yourself, or give it to your AI coding assistant as context together with the repository. Each fix says what to change, where, and why, so the assistant does not have to guess the intent.

**What is confirmed and what is not.** The audit had the scripts and the published data files, but not `data_raw/`. Anything marked *confirm on data first* was inferred from code and summary numbers and should be checked on the pixel stack before it is fixed.

**Three working rules.**

1. Line numbers below are from commit `f8f5ce8` and may have moved. Search for the quoted text instead of trusting the number.
2. `alerts.json` and `places.geojson` are written by the monitor script. Change the strings in the script as well as in the JSON, or the next run restores the old wording.
3. `layers.json` is edited by hand. After any re-run, re-check every number in its text against `stats.json`.

**Order of work.**

| Step | What | Needs |
|---|---|---|
| 1 | Text fixes F1 to F13 | Nothing. Edit and deploy. |
| 2 | UI fixes U3 and U4 | Code only. |
| 3 | M1 (imaging modes) | Raw data, re-run. Do before any other method fix, because it changes their inputs. |
| 4 | M2, M3, M4, M5, M6 | Raw data, re-run. |
| 5 | U1 and U2 | Tiles rebuilt. |
| 6 | Update the text again with the new numbers | After the re-runs. |

Step 1 alone removes every overstated claim from the live site.

## Files involved

| File | Role |
|---|---|
| `public/data/layers.json` | Layer titles, explain and caveat text, legends. Hand-edited. |
| `public/data/alerts.json`, `places.geojson` | Alert text. Written by `coastlens_monitor.py`. |
| `public/data/zones.geojson`, `stats.json` | Decline zones and all computed statistics. |
| `scripts/nisar/nisar_pixel_stack.py` | Builds the 20 m pixel stack; records the imaging mode per date. |
| `scripts/nisar/nisar_pixel_products.py` | Trend, structural-vs-moisture, land-cover classes, AI map. |
| `scripts/nisar/nisar_timeseries.py` | Scene selection rule, zone time series, coherence quality check. |
| `coastlens_monitor.py` | Builds alerts, signal counts, ranking, next-pass date. |
| `scripts/ee/export_layers.js` | Earth Engine exports (optical, Sentinel-1, ALOS). |
| `docs/nisar_scenes_rehri_goth.csv` | Granule list with names and URLs. |
| `src/map.js`, `src/styles.css` | Map page behaviour, popup, legend, story text. |

## Facts the fixes rely on

**The 27 passes (track 164, descending, frame 76, all at about 14:06 UTC):**

| Dates | Mode | Collection |
|---|---|---|
| 21 Nov, 15 Dec, 27 Dec 2025; 8 Jan, 20 Jan, 1 Feb, 13 Feb, 25 Feb, 9 Mar, 2 Apr, 26 Apr, 20 May, 13 Jun, 7 Jul, 24 Aug, 17 Sep, 11 Oct 2026 (17) | 2005, quad-pol, 20 m | Provisional, CRID P05023 |
| 3 Dec 2025; 21 Mar, 8 May, 1 Jun, 25 Jun, 19 Jul, 12 Aug, 5 Sep, 29 Sep 2026 (9) | 4005, dual-pol, 10 m | Provisional, CRID P05023 |
| 23 Oct 2026 (1) | 4005, dual-pol | Validated, CRID P05036 |

14 Apr 2026 exists but is removed by the coherence quality check. 31 Jul 2026 falls in the instrument gap.

**Coherence pairs (track 142):** the Dec 2025 pair is a BETA product (CRID X05010); the Sep 2026 pair is PROVISIONAL (CRID P05023).

---

# Part 1. Text fixes (no data needed)

Each entry gives the current wording, the suggested wording, and where it lives. Adjust the phrasing to your own voice; keep the meaning.

## F1. Stop calling the alerts "mangrove thinning" (P1)

**Why.** An alert is a patch whose HV signal fell about 1.4 to 1.9 dB/yr relative to the forest median. That is roughly 1.3 to 1.7 dB over the 0.92 years of data, below the 2 dB the structural-vs-moisture layer needs to count a change. The structural signal is false for all 8 alerts. "Thinning" states a cause the data has not shown.

| Where | Current | Suggested |
|---|---|---|
| Alert title (`coastlens_monitor.py` near line 231; `alerts.json`; `places.geojson`) | "Alert N: mangrove thinning" | "Alert N: radar signal weakening (not field-checked)" |
| Page intro (`src/` map page text) | "Pink dots are NISAR alerts: patches thinning now." | "Pink dots are NISAR alerts: patches where the radar signal weakened this year. They need a field check." |
| Map legend label | "Thinning now: check here first" | "Radar weakening: check here first" |
| Story 05 button | "What is thinning right now" | "Where the radar signal is weakening" |
| Story 05 text | "...patches where the forest is getting thinner right now, backed up by other satellites too. That is where conservation teams should look first." | "...patches where the forest's radar signal weakened this year compared with the rest of the forest. Older records show past loss near most of them. They are leads for a field visit, not confirmed damage." |

Add one sentence to the trend layer's explain text so the two layers no longer look contradictory:

> "This differs from the structural layer, which only counts changes of 2 dB or more between two short windows. The alerts flag smaller, steady declines of about 1.5 dB per year relative to the forest."

## F2. Remove the bare "statistically significant" (P2)

**Why.** The per-pixel test is an ordinary least-squares slope with |t| ≥ 2, not corrected for season, autocorrelation or the number of pixels tested. About 27,400 of 485,300 pixels pass by chance. The phrase is printed for every alert unconditionally (`coastlens_monitor.py` near lines 217 to 218).

| Where | Current | Suggested |
|---|---|---|
| Alert "Observed" text | "(-1.5 dB/yr vs the rest of the forest, statistically significant)" | "(-1.5 dB/yr vs the rest of the forest; a steady decline through the year)" |
| `alerts.json` `method` string | "(\|t\| >= 2)" | "(\|t\| >= 2 per pixel, not corrected for season or for testing many pixels)" |

After M2 is done, replace this with the measured figure, for example "8 alerts found; about N expected by chance".

## F3. Reword "3 of 4 independent signals" and "High" (P3)

**Why.** `nisar_now` is hard-coded true for every candidate (`coastlens_monitor.py` near line 195), so it is an entry condition, not evidence. GMW v4.1 uses JAXA L-band radar as an input, so GMW loss and an ALOS-2 drop are not independent. "8 of 8 High" follows from sorting by signal count and keeping the first 8.

| Where | Current | Suggested |
|---|---|---|
| Alert "Confidence" | "High (3 of 4 independent signals agree). Not field-checked." | "NISAR trend plus 2 of 3 supporting records. The GMW and ALOS-2 records share L-band data, so they count as related evidence. Not field-checked." |
| Popup header | "NISAR ALERT · HIGH PRIORITY" | "NISAR ALERT · FOR FIELD CHECK" |
| `alerts.json` `method` string | "ranked by how many of 4 independent signals agree" | "ranked by how many of 3 supporting records agree (GMW and ALOS-2 overlap), then by size; the 8 largest shown" |

Keep "High / Medium / Low" off the page until M3 gives the labels a real basis.

## F4. Correct "season, tide and calibration shifts cancel out" (P4, P16)

**Why.** Dividing each pass by the forest median removes only what is common to the whole forest. A pixel whose seasonal or tidal response differs from the forest's gets a slope with no canopy change. Tide is not used anywhere in the pipeline.

Trend layer explain text (`layers.json` near lines 212 to 213):

- Current: "...compared with the forest as a whole on every pass (so season, tide and calibration shifts cancel out)."
- Suggested: "...compared with the forest as a whole on every pass, so shifts that affect the whole forest equally (such as calibration) cancel out. Patches that respond differently to season or tide do not cancel."

Add to the caveat:

> "Tide height at each pass has not been checked yet. Random noise alone would flag roughly 1 to 3% of the forest on each side; the rest is a real pattern in the data but is not proven to be canopy change."

The 1 to 3% is the audit's analytic estimate (0.6% to 2.8%). Replace it with the shuffle result from M2 when available.

## F5. "Two years before optical" becomes "about a year" (P5)

**Why.** From `stats.json › zone_history`, zone C: the 2016 drop (1.1 dB) is matched by a 0.9 dB drop in the stable reference forest, so it is a mosaic-wide shift. Relative to the reference, the first clear drop is 2017. NDVI falls in the season labelled 2018, which is Nov 2017 to Feb 2018. GMW also shows shrinkage from 2017.

| Where | Current | Suggested |
|---|---|---|
| ALOS-2 2024 layer explain (`layers.json` near line 701) | "In decline zone C it showed the forest thinning from 2016, two years before optical satellites saw it..." | "In decline zone C its signal dropped against stable forest from 2017, about a year before the greenness drop..." |
| Story 06 text | "...it showed the forest thinning in 2016, two years before ordinary photos noticed." | "...it showed the forest weakening in 2017, about a year before ordinary photos noticed." |

## F6. Source or soften "much of it planted" (P6)

**Why.** No analysis in the repo separates planted from natural gain, and the map gives no citation. `SOURCES.md` lists Ahmed et al. 2025 with the note "taken from the abstract; read the paper".

Options, best first:

1. Read the paper, confirm it supports the statement for this stretch of coast, then write "partly through planting (Ahmed et al. 2025)" and link it.
2. If it only covers the wider Indus Delta: "Planting programmes have expanded mangroves in the wider Indus Delta (Ahmed et al. 2025); how much of the gain here was planted is not measured."
3. Remove the clause.

Apply the same choice in the GMW 1985 → 2025 layer text (`layers.json` near line 376) and in story 04.

## F7. Past tense for the decline zones (P7)

**Why.** `zones.geojson` gives 6 of 7 zones the status "no extra weakening seen by NISAR this year". The losses in GMW were mainly between about 2011 and 2020.

| Where | Current | Suggested |
|---|---|---|
| Story 02 button | "Places that keep dying" | "Places that kept shrinking" |
| Legend label | "Area that keeps losing forest" | "Area that lost forest year after year" |

Optional: show each zone's `status` field from `zones.geojson` when a zone is clicked. It is already computed and is a useful, careful statement.

## F8. HH layer source field (P8)

`layers.json` near line 113, layer `nisar_hh_20261011`: change `NISAR_L2_GCOV_V1` to `NISAR_L2_GCOV_PROVISIONAL_V1`. The granule is `..._20261011T140554_..._P05023_...`.

## F9. Coherence layers (P9)

- `resolution`: "20 m" becomes "20 m grid". The values come from the `frequencyA/wrappedInterferogram` grid; the true resolution of a coherence estimate is coarser than its spacing.
- Dec 2025 layer `sensor`: add "(beta product)".
- Sep 2026 layer explain: replace "Compare with December: wetter, more changeable surfaces lose coherence." with "Wetter, more changeable surfaces lose coherence. The December layer is an earlier beta product, so differences between the two can come from processing as well as season."
- Add to both caveats: "Values below about 0.25 are within the noise of this measurement." (The script notes a noise floor of about 0.24, `nisar_timeseries.py` near line 165.)

Better, if available: check `docs/nisar_scenes_rehri_goth.csv` or ASF for a PROVISIONAL GUNW pair in December 2025 and rebuild that layer from it. Then both layers have the same maturity.

## F10. State the pass inventory once, the same everywhere (P10)

- In the `sensor` field of the multi-pass analysis layers, replace "(L2 GCOV, provisional)" with "(L2 GCOV; 27 passes: 26 provisional, 1 validated)".
- In `docs/resources-used.md` and `SOURCES.md`, replace "28 GCOV passes" with "28 passes listed, 27 used (14 Apr 2026 removed by quality check)".

## F11. Explain the mangrove areas (P11)

**Why.** 180.9 km² is GMW on its own grid inside the lat/lon box. 184.36 km² is GMW resampled onto the NISAR 20 m UTM grid, whose rectangle is slightly larger than the box. The AI map is 194.12 km².

- Land-cover layer explain (`layers.json` near line 295): "(GMW 2025: 184.36 km²)" becomes "(GMW 2025 on the same grid: 184.36 km²; 180.9 km² on GMW's own grid)".
- Story 01: "Karachi's coast has about 181 km² of them. The green on the map is where NISAR, a radar satellite, finds them." becomes "Global Mangrove Watch maps about 181 km² of them on Karachi's coast. The green on the map is where our NISAR radar model finds them: about 194 km², a little more because it includes some edge pixels."

Cleaner long-term fix (needs a re-run): clip the NISAR grid to the lat/lon box so one GMW number serves both.

## F12. AI map accuracy text (P12)

**Why.** Accuracy is measured only on pixels GMW is sure about (over 90% or under 10% mangrove). Precision is 91.8% and F1 is 0.942. The audit rebuilt these from the published percentages and pixel counts; they are not stored. The published map and its 194.12 km² come from a second model trained on the whole box, at the default 0.5 threshold.

Suggested explain text:

> "...Tested on 2 km map blocks it never saw, on pixels where GMW is sure: 95.7% accurate. It finds 96.7% of GMW's mangrove, and 91.8% of what it marks is GMW mangrove (F1 0.94). The map shown comes from a model trained on the whole box and maps 194.12 km² (GMW on the same grid: 184.36 km²)."

When you next re-run, store the confusion matrix in `stats.json` so these numbers are written by the script.

## F13. Rule-based map caveat (P13)

"Simple thresholds tuned on Rehri Goth" becomes "Simple thresholds set by eye on the Rehri Goth sub-area (about 2% of the box); agreement measured over the whole box".

## Already fixed

The alerts' "NISAR checks again around..." date was in the past during the audit and now shows a future date. If that was a hand edit, also fix the logic in `coastlens_monitor.py` (near lines 167 to 168): roll `next_pass` forward in 12-day steps until it is after today, and if a pass is overdue print "pass of <date> not yet published". Then check ASF for track 164 granules after 23 Oct 2026 and ingest any that exist.

---

# Part 2. Method fixes (need the raw data and a re-run)

Rebuilding the stack needs `nisar_pixel_stack.py`, the Earthdata token and about 1 GB of downloads (20 to 45 MB per pass).

## M1. Two imaging modes in one series (P14). Do this first.

**The issue.** 17 passes are quad-pol (mode 2005) and 10 are dual-pol (mode 4005). On the 80 m zone means, each dual-pol pass reads lower than its two quad-pol neighbours: mangrove HH by 1.34 dB (s.d. 0.13), land HH by 1.05 dB, HV by about 0.3 dB, while water HV reads 0.92 dB higher. The stack records the mode per date (`nisar_pixel_stack.py` near line 69) but nothing reads it.

**Step 1. Confirm on the 20 m stack.**

- Pick stable pixels: land or built-up pixels whose quad-pol-only time series has a small spread (for example s.d. under 0.7 dB), away from water and creek edges.
- For each dual-pol pass that sits between two quad-pol passes, compute per polarization: median over the stable pixels of (dual-pol pass, dB) minus (mean of the two neighbours, averaged in linear power then converted to dB).
- Report the offset per pass and its spread, separately for stable land, mangrove and water. A steady offset (spread around 0.2 dB or less) is an instrument or processing effect.
- Rule out your own processing first: dual-pol is 10 m native and quad-pol 20 m. Check that gridding to 20 m averages in linear power for both, that both read the same GCOV dataset and the same gamma0 convention, and that no mode is multilooked twice.
- The opposite sign over water suggests the two modes have different noise floors. Check the product metadata and the NISAR known-issues notes before assuming a simple constant offset holds for dark targets.

**Step 2. Choose a fix.**

- **Option A, single mode for the structural layer (simplest).** Build the two windows from quad-pol passes only: early = 21 Nov, 15 Dec, 27 Dec 2025; late = 24 Aug, 17 Sep, 11 Oct 2026. All six are quad-pol and all provisional P05023, so this also removes the mixed-maturity question for that layer.
- **Option B, per-mode offset.** Estimate one offset per polarization from the stable pixels and remove it from the dual-pol passes before any step that uses HH. Store the offsets and their spread in `stats.json` and state them on the page.
- **Option C, quad-pol only for yearly features.** Compute the yearly HH mean, HH spread and HV-minus-HH features from the 17 quad-pol passes.

A and C together are the least risky for a deadline.

**The HV trend.** The per-pass forest median already removes a uniform offset. To be safe, add the mode as a covariate in the per-pixel regression: residual = a + b·t + m·(1 if dual-pol else 0). The modes alternate, so the mode term is almost uncorrelated with time and costs little. Then check that the mean residual per mode is near zero in each class.

**Done when:** the HH zone series no longer shows a saw-tooth, and the structural layer's statistics are reported with the window dates and modes.

## M2. Trend layer and "significance" (P2, P4)

**What the code does now** (`nisar_pixel_products.py` near lines 224 to 251): for pixels in the forest mask with at least 10 dates, subtract the per-pass forest median (dB), fit an ordinary least-squares line against time over 0.92 years, and flag slope ≤ −1 or ≥ +1 dB/yr with |t| ≥ 2. Alerts use 100 m cells with at least 8 forest pixels of 25 and at least 40% of them weakening (`coastlens_monitor.py` near lines 126 to 131).

**Step 1. Measure the false-flag rate with a shuffle test.**

- For every pixel, randomly permute the order of its residual values across the dates, refit, and apply the same flag rule.
- Repeat about 20 times over the whole raster and average the flagged fraction per side. That is the share noise alone would flag.
- Run each shuffled raster through the identical alert pipeline (100 m cells, 40% rule, patch size, 500 m spacing) and count the alerts. That gives "alerts expected by chance".
- Publish both pairs: observed 10.5% and 16.3% against the shuffled figures, and 8 alerts against the expected count.

Note what the shuffle does not cover: it destroys seasonal shape, so it measures noise, not the seasonal effect below.

**Step 2. Deal with season. A regression term will not do it.** With under one year of data, a straight line and a one-year sine wave are almost the same shape, so adding a seasonal term to the fit cannot separate them. Use one of these instead:

- **Same months, one year apart (best).** Once Nov and Dec 2026 passes are published, compare the Nov to Dec 2025 mean with the Nov to Dec 2026 mean, same mode on both sides (see M1). Season cancels by design. This can replace the slope as the alert measure.
- **Compare like with like.** Instead of one forest-wide median, group pixels by how they behave (for example by quartile of HV seasonal spread, or of HH spread as a proxy for tidal flooding) and subtract the median of the pixel's own group on each pass.
- **Tide as a covariate.** See M5.

**Step 3. Make the test match its claim.**

- Autocorrelation: estimate the lag-1 autocorrelation r of the residuals and use an effective sample size n_eff = n·(1 − r)/(1 + r) when computing t, or use a block permutation.
- Many tests: set the cell-level threshold from the shuffled runs so the expected number of chance alerts is below one, or apply a false-discovery-rate correction (Benjamini–Hochberg) to the per-cell p-values.
- Shared noise: the 3×3 speckle filter makes neighbours share noise, so the count of independent pixels is about one ninth of the pixel count. Require patches clearly larger than the filter footprint.

**The asymmetry.** Strengthening (16.3%) exceeds weakening (10.5%) and the median slope is +0.13. A measure relative to the forest should centre on zero. After the fixes above, check that it does; if not, look for a systematic shape effect (for example the mask, see M4).

**Done when:** the page states observed against expected-by-chance, and the word "significant" appears only if the corrected test supports it.

## M3. Alert signals and ranking (P3)

**Restructure the evidence.**

- Treat the NISAR trend as the **entry condition**, not as a signal.
- Merge `gmw_history` and `lband_longterm` into one **long-term record** signal, since GMW v4.1 uses JAXA L-band.
- Add one signal from a different kind of measurement: **optical greenness**. For example, the share of the patch where dry-season NDVI (Landsat or Sentinel-2, already exported) fell by more than a set amount between two periods.
- Keep **Sentinel-1 C-band drop** and **NISAR structural change** as separate signals.

**Tighten each rule.**

- ALOS-2 drop: divide each yearly mosaic by the forest median before differencing. The 2016 mosaic shifts by about 0.9 dB everywhere, and two single unfiltered mosaics are noisy. Apply a light speckle filter.
- GMW loss nearby: use a fixed distance from the patch edge and a loss area relative to the patch area. The current bounding-box-plus-200 m window grows with the patch, so large patches pass more easily.
- Report the **base rate** of every signal: what share of all forest 100 m cells meets it. A condition that a third of the forest meets is weak evidence. Alert values of 26% to 44% against a 25% threshold only mean something next to that base rate.

**Make the ranking visible.**

- Write the number of candidates and the histogram of signal counts into `alerts.json`.
- Show "8 of N candidates" on the page.
- Derive priority from a fixed rule (for example, entry condition plus at least 2 of the 3 different signal families), not from position in a sorted list.

## M4. Independent forest mask for the trend (P15)

**The issue.** The trend mask is AI probability ≥ 0.5 (`nisar_pixel_products.py` near line 222), and the AI features are the same year's HV mean, low and high values and spread. Pixels that lost canopy early can drop out of the mask and never be tested.

**Fix, either of:**

- Use GMW 2025 resampled to the NISAR grid (for example at least 50% mangrove) as the trend mask.
- Train the mask model on the first three or four months only, and test the trend on the rest.

Report how many pixels differ between the old and new masks, and whether the weakening and strengthening shares move.

## M5. Tide (P16)

**The issue.** Every pass is at about 14:06 UTC. A fixed clock time every 12 days samples the spring-neap cycle with a repeat of about 64 days, so water level at overpass varies strongly between passes. L-band HH under mangrove depends on the water surface.

**Steps.**

1. Make a small table `tide_at_pass.csv`: date, time (UTC), predicted tide height, source. Use a tide model through `pyTMD` (the model files need a separate download), or published tide predictions for Karachi or Port Qasim. For 27 dates a manual table is fine.
2. Correlate tide height with the per-pass forest median of HH, HV and HV minus HH. Report the correlation coefficients.
3. For each alert patch, correlate its residual series with tide. A strong correlation means the "trend" may be tide sampling.
4. Add tide as a covariate in the per-pixel regression: residual = a + b·t + c·tide. With about five tide cycles in the series, tide and time are not confounded.
5. Show the tide height beside the time-series chart, and say on the map what was found.

## M6. Average in linear power in the last three places (P17)

In `nisar_pixel_products.py`:

- "HV 60 m mean" feature (near line 187): box-filter the linear power, then convert to dB.
- "HV texture 100 m" (near line 148): compute the spread on linear power (or coefficient of variation), or keep dB but document it; it also sets a class threshold.
- Structural-vs-moisture 60 m smoothing (near line 262): smooth the early and late windows in linear power, then take the dB difference.

Expect small changes. Re-check the class thresholds and retrain the AI model afterwards.

---

# Part 3. Display and UI fixes

## U1. HH colour range (P18)

HH uses −25 to −5 dB, the HV range (`nisar_pixel_products.py` near lines 93 and 137 to 140). Mean HH is −6.3 dB in mangrove and about −4.5 dB on land, so most of the image is white.

- Measure the 2nd and 98th percentiles of HH inside the study box and set the range from them. Start from −20 to 0 dB.
- Rebuild the HH tiles and update the legend ends in `layers.json` (near lines 127 to 128).
- Keep HV at −25 to −5 dB and say in the HH text that the two layers use different ranges.

## U2. One colour rule for change layers (P19)

Current: HV change uses red-white-blue; the trend and NDVI change use red-white-green. Class layers add blue for GMW gain and for "wetter".

- Use red for decrease and blue for increase on every continuous change layer. Red and blue stay distinguishable for colour-blind readers and carry no "good or bad" meaning.
- Keep green for vegetation classes only.
- That changes two layers (trend, NDVI change): update the colour ramps in the scripts, rebuild their tiles, and update the legends in `layers.json` and the story legends in `src/map.js`.

## U3. Alert popup (P20)

`src/map.js` (popup created near line 40, `maxWidth: 340`) and `src/styles.css` (near lines 367 to 375).

- Give the Leaflet popup a `maxHeight` (for example 300) so long content scrolls inside it, and `autoPanPaddingTopLeft` (for example `[56, 16]`) so it does not open under the zoom buttons.
- At 860 px and below, do not use a map popup. Show the alert details in a block directly under the map and scroll it into view. A full alert has six text rows and will not fit over a 60vh map.
- Hide the legend box while a popup is open (`popupopen` / `popupclose` events).
- Remember the map centre before the popup opens and pan back on close, so the study area is not left off-screen.
- Add `overflow-wrap: anywhere` to the popup text so coordinates do not overflow.

## U4. Legend box (P21)

- Add a small toggle to collapse the "What the colours mean" box, collapsed by default on narrow screens.
- Cap its height and let it scroll when several layers are on, or move it below the map at 860 px and below.
- The per-layer legend is already in the side panel, so the box on the map can show only the zone and alert symbols when more than two layers are active.

---

# Keeping numbers in sync

Every number in `layers.json` currently matches `stats.json`, but only because it was copied by hand. After the re-runs above, many will change. Either:

- generate the explain-text numbers from `stats.json` at build time (placeholders in the text, filled by a small script), or
- add a check script that reads each number in `layers.json` and fails the build when it differs from `stats.json`.

Three statements currently have no script output behind them: "about 3.5 dB too dark" for the beta file (the code comment says about 3 dB), "much of it planted" (F6) and "two years before" (F5). Give each a source or a computed value.

# Final checklist

- [ ] No alert, legend, intro or story says "thinning" without a field check or a structural signal (F1).
- [ ] "Statistically significant" is gone or backed by M2 (F2).
- [ ] No text calls the GMW and ALOS-2 records independent (F3).
- [ ] The trend layer no longer says tide cancels out (F4).
- [ ] Zone C says "about a year" (F5); the planting claim has a citation or is removed (F6).
- [ ] HH source field corrected (F8); coherence layers say "20 m grid" and "beta" (F9).
- [ ] Pass inventory stated once and consistently (F10); mangrove areas explained (F11).
- [ ] AI text shows precision and F1 (F12).
- [ ] Imaging-mode offset confirmed and handled (M1).
- [ ] Observed versus expected-by-chance published for the trend and alerts (M2).
- [ ] Alert candidates, base rates and ranking rule published (M3).
- [ ] Trend mask is independent of the tested data (M4).
- [ ] Tide table added and correlation reported (M5).
- [ ] HH range fixed (U1), one colour rule (U2), popup and legend work at 375 px (U3, U4).
- [ ] Every number in the layer text re-checked against `stats.json` after the last re-run.
