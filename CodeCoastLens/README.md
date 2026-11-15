# CoastLens

**Watching the mangroves of Karachi's coast with NASA-ISRO's NISAR radar satellite.**
NASA Space Apps Challenge 2026, challenge "Dancing with the SARs". An independent student project from FAST-NUCES Karachi.

This README has two parts:

- **[Part 1: What the website shows](#part-1-what-the-website-shows)**, in plain language. Use it to present the site, especially the Map page.
- **[Part 2: Technical reference](#part-2-technical-reference)**, the facts, methods and numbers behind Part 1, plus how the whole thing was built. Use it to answer questions.

Every number below comes from `public/data/stats.json` or `public/data/alerts.json`, which the scripts in `scripts/` write. If you re-run the pipeline, re-check the numbers here.

---

# Part 1: What the website shows

## The idea in three sentences

Mangroves are trees that grow in seawater. They shelter young fish and shrimp, protect the shore from waves and storms, and store carbon. Karachi's mangroves are mapped as growing overall, but a few pockets have been shrinking for years. CoastLens uses NISAR, a radar satellite that sees through cloud and works at night, to watch the coast every 12 days and point people on the ground to places worth checking.

## The study area

One box on Karachi's coast, **from Rehri Goth to Port Qasim and the creeks to the south**: about 28 × 17.5 km (about 490 km²). Every number on the site is measured inside this box.

## The six pages

| Page | What it is for |
|---|---|
| **Home** | A radar lens that sees through the clouds, a 3D mangrove to explore, a fish's journey from the roots to your plate, why clouds blind ordinary cameras, and the paradox: on paper the forest is growing back, on the ground the sea still takes homes. Then the **impact map** (below) as proof, the delta's story, the five UN goals mangroves touch, and a closing call. |
| **NISAR** | How radar works: a 3D model of the satellite with its parts named, the main points at a glance, animations of how radar sees through cloud and night, why water is dark and forest bright, a real photo-vs-radar comparison, the 12-day repeat, what radar cannot tell you, and a short glossary. |
| **Insights** | Three findings, each laid out as *what was measured*, *possible explanation* and *confidence*. Then a compare-the-layers tool and the eight alerts. |
| **Map** | Every layer in one place, six guided stories, the decline zones and the alerts. This is the main page to present (see below). |
| **Collaborators** | Our confirmed collaborators (Saltwater Marina, Mangrove Crew), organisations working in the Indus Delta, and three things only people on the ground can give us: planting records, field checks of the alerts, and interviews (with consent). |
| **About us** | The team (six Computer Science students), our rules about what we will and will not claim, and where every number comes from. |

## The impact map on the Home page

Under "So we checked from space." the home page shows one fixed map, with no buttons or layers to change. It is the proof that there is a problem:

- The background is our own Sentinel-2 photo of the coast east of Rehri Goth, around Port Qasim.
- Coloured patches are mangrove that was there and is now gone, coloured by the year it was lost (yellow long ago, red recently).
- Pink dashed outlines are the decline zones, where the forest kept shrinking year after year. The worst, zone A, is labelled.
- *Say:* "Across the whole coast the mapped forest grew. But in seven small zones it kept shrinking. In the worst one, 0.78 km² of mangrove in 2008 became 0.16 km² by 2025, a loss of 80%." Then click **Explore the full map**.

## Presenting the Map page

**How the page is laid out.** On the left: a short intro, six numbered stories, a basemap choice and the full list of layers. On the right: the map. The background inside the box is our own cloud-free Sentinel-2 photo from the 2025–26 dry season. The box at the bottom right, "What the colours mean", explains whatever is showing (click its title to fold it away).

**Two things are always on the map:**

- **Pink dashed outlines = decline zones.** Seven small places where Global Mangrove Watch shows the forest shrinking year after year, mostly between about 2011 and 2020. Hover over one to see how much it lost.
- **Pink dots = NISAR alerts.** Eight patches where the mangrove's radar signal weakened this year compared with the rest of the forest. Click one to see the evidence. **An alert is a place to go and look, not proof of damage.**

### Walk through the six stories

Click each story button in order. The map flies to the right place and switches on the right layers.

**01 · Where are the mangroves?**
Shows our AI mangrove map, made from NISAR radar alone. *Say:* "Global Mangrove Watch maps about 181 km² of mangrove in this box. The green is where our radar model finds them, about 194 km². It is a little more because it includes some edge pixels. Darker green means the model is more certain."

**02 · Places that kept shrinking**
Zooms to the two largest decline zones and colours each lost patch by the year it disappeared (yellow long ago, red recently). *Say:* "Most of this coast is greener than 40 years ago, but in the worst zone about four-fifths of the forest is gone since 2008, from 0.78 to 0.16 km². When mangroves go, the shore behind them loses its shield."

**03 · Seeing through clouds**
Shows a NISAR radar image over Rehri Goth. Use the slider in the legend box to fade between the photo and the radar. *Say:* "Clouds and night hide the forest from cameras, often in the monsoon, which is exactly when storms hit. Radar sees through both. Bright means a strong echo (trees, buildings), dark means water."

**04 · 40 years of change**
Blue is new mangrove since 1985, red is mangrove that was lost. *Say:* "The forest in this box grew from about 67 km² in 1985 to about 181 km² in 2025. Planting programmes have expanded mangroves in the wider Indus Delta, but how much of the gain *here* was planted is not measured. A big total can hide the places that lost their forest, which is why we look closer."

**05 · Where the radar signal is weakening**
Shows the "forest watch" layer and the eight alerts. Red is where a patch's radar signal weakened against the rest of the forest, blue is where it strengthened. *Say:* "NISAR passed over this coast 27 usable times in one year. The eight dots are the largest of 120 patches where the signal weakened. If the data were pure noise we would expect about one. They are leads for a field visit, not confirmed damage: the cause could also be season or tide, and older satellite records do not single these places out yet. That is why we want people on the ground."

Then **click a pink dot**. The popup shows what NISAR measured, what older records say, how much evidence agrees, whether the patch follows the tide, possible causes to check, and a Google Maps link. On a phone the same details open in a card under the map.

**06 · Old satellite vs NISAR**
Compares the older Japanese L-band radar (ALOS-2, one picture a year) with NISAR (a picture every 12 days). Use the slider. *Say:* "In decline zone C the old radar saw the forest weakening in 2017, about a year before ordinary photos noticed. But one picture a year is slow. NISAR checks every 12 days, so a problem can be caught while there is still time to act."

### The full layer list (if someone asks to see more)

30 layers in five groups. Tick any layer to see its explanation, a caution note in pink, and where the data comes from.

| Group | What is in it |
|---|---|
| **NISAR radar (L-band)** | Single radar images (HV 21 Nov 2025 and 11 Oct 2026, HH 11 Oct 2026) and two "coherence" layers showing how much the surface changed in 12 days (dry season and end of monsoon). |
| **Mangrove extent** | Global Mangrove Watch maps for 1985 and 2025, gain and loss 1985–2025, and the year each lost patch disappeared. Older GMW v3 maps are kept to show that older products disagree with each other. |
| **Optical imagery** | Landsat and Sentinel-2 true-colour photos (2015 to 2026) and vegetation greenness (NDVI). |
| **Older radar satellites** | ALOS / ALOS-2 L-band (2010, 2024) and Sentinel-1 C-band (2017–18, 2025–26), for comparison with NISAR. |
| **Our analysis** | AI mangrove map, forest watch (the trend), structural vs moisture change, HV change, rule-based land cover, greenness change. |

**Colours follow one rule.** On every change layer, red means a decrease and blue means an increase. Green is used only for mangroves and vegetation. Pink is used only for warnings (zones and alerts).

## The honest summary (good closing line)

- The forest in the box has nearly tripled since 1985, but seven small zones lost most of their forest.
- One year of NISAR shows a real pattern of patches weakening and strengthening against the rest of the forest. It is not yet proof of damage.
- The eight alerts are where we would send a field team first. A second year of NISAR, at the same season, will tell trend from season.

---

# Part 2: Technical reference

## 1. Data used

| Data | What and when | Used for |
|---|---|---|
| **NISAR L2 GCOV** (backscatter) | Track 164 descending, frame 76, every 12 days, about 14:06 UTC (19:06 Pakistan time). 28 passes listed from 21 Nov 2025 to 23 Oct 2026; **27 used** (14 Apr 2026 removed by a quality check). 26 provisional (processing version P05023), 1 validated (23 Oct 2026, P05036). 17 quad-pol (mode 2005, 20 m) and 10 dual-pol (mode 4005, 10 m). | Every NISAR layer, the AI map, the trend, the alerts |
| **NISAR L2 GUNW** (interferogram) | Track 142 ascending, frame 14. Pairs 14–26 Dec 2025 (**beta**, X05010) and 4–16 Sep 2026 (provisional). | The two coherence layers |
| **Global Mangrove Watch v4.1** | Yearly 1985–2025, tile N25E067 (Zenodo 21346457) | Mangrove history, decline zones, labels for the AI model, the trend's forest mask |
| **JAXA ALOS / ALOS-2 PALSAR** | Yearly L-band mosaics 2007–2010 and 2015–2024 (Earth Engine) | The L-band record before NISAR |
| **Sentinel-1 GRD** | C-band VH, 2016–2026 (Earth Engine) | Comparison with L-band |
| **Landsat 5/7/8/9, Sentinel-2** | Dry-season (Nov–Feb) cloud-masked medians (Earth Engine) | Photos, NDVI, the water mask |
| **GOT4.10 tide model** (NASA GSFC, via pyTMD) | Predicted tide height at every NISAR pass, at 24.65 N 67.15 E | Tide check on the trend (`docs/tide_at_pass.csv`) |

NISAR files are about 6 GB each. We never download them whole: `scripts/nisar/remote_h5.py` reads only the bytes for our box over HTTPS (20 to 45 MB per pass).

## 2. Key numbers

| Figure | Value |
|---|---|
| Mangrove in the box, GMW v4.1 | 67.22 km² (1985) → 180.9 km² (2025), +169.1% |
| Same 2025 GMW, resampled onto the NISAR 20 m grid | 184.36 km² (that grid covers a slightly larger rectangle) |
| Mangrove lost and not come back, 1986–2025 | 5.78 km² |
| Decline zones | 7. Largest: zone A, 0.78 km² (2008) → 0.16 km² (2025), −80%. All lost 63% to 83%. |
| AI mangrove map | 194.48 km² |
| AI map accuracy (held-out 2 km blocks) | 95.4% accurate; finds 96.6% of GMW mangrove (recall); 91.3% of what it marks is GMW mangrove (precision); F1 0.94 |
| Rule-based land-cover map | 156.49 km² of mangrove; 85.0% agreement with GMW (recall 72.8%, precision 83.4%) |
| Forest watch (trend) | 8.5% of the forest (15.67 km²) weakening by more than 1 dB/yr; 13.4% strengthening. Noise alone: about 0.6% each way. |
| Structural canopy loss inside the forest, Nov–Dec 2025 vs Aug–Oct 2026 | 0.02% of the forest |
| Alerts | 8 shown out of 120 candidate patches (4.2 to 11.7 ha each). Expected from noise alone: 0.65 on average. |
| Greenness (NDVI) inside mangroves | 0.479 (2015–16) → 0.558 (2021–22) → 0.513 (2024–25) |
| Mangrove vs non-mangrove separation, same pixels (AUC) | Landsat NDVI 0.991; Sentinel-1 VH 0.918; ALOS-2 HV 0.869; NISAR HV alone 0.892; NISAR AI model 0.992 |

## 3. Methods, layer by layer

### Pixel stack
`nisar_pixel_stack.py` reads HH and HV for every pass onto one fixed 20 m UTM 42N grid (890 × 1419 pixels). Values are averaged in **linear power** (never in dB) so the 10 m dual-pol and 20 m quad-pol modes line up. A 3×3 speckle filter is applied before analysis.

### Two imaging modes
Track 164 alternates quad-pol and dual-pol passes (from March 2026 they alternate pass by pass). On the same grid, a dual-pol pass reads differently from the two quad-pol passes around it, and **the difference depends on the surface**:

| Surface | HH, dual minus quad | HV, dual minus quad |
|---|---|---|
| Stable land | −0.38 dB | −0.11 dB |
| Mangrove | −0.60 dB (spread 0.15) | −0.10 dB |
| Open water | +0.84 dB | +1.32 dB |

The control (a quad-pol pass compared with its quad-pol neighbours) is about 0 dB, so this is an instrument or processing effect, not the landscape. Because one constant cannot fix all surfaces, **everything that uses HH or a yearly average uses only the 17 quad-pol passes**. The HV trend uses all 27 passes with the mode as an extra term in the fit.

### AI mangrove map (Random Forest)
- **Features (10, NISAR only):** yearly HV mean, HH mean, HV−HH, HV low (10th percentile), HV high (90th), HV and HH seasonal spread, HV–HH correlation, HV texture over 100 m, HV mean over 60 m. The most important are HV low, HV 60 m mean and HV mean.
- **Labels:** GMW 2025, only on pixels GMW is sure about (over 90% or under 10% mangrove).
- **Test:** the map is split into a checkerboard of 2 km blocks. The model is trained on one colour and tested on the other, then swapped. Neighbouring pixels never sit on both sides, so the test is fair.
- **Confusion matrix (pixels):** both mangrove 424,348 · NISAR only 40,592 · GMW only 15,142 · both not 740,184.
- **The published map** comes from a second model trained on all sure pixels in the box, mangrove = probability ≥ 0.5.
- **Limits:** mixed creek-edge pixels are left out of the test, and the model inherits GMW's own errors.

### Rule-based land-cover map
Thresholds on a year of quad-pol HV and HH: water/mudflat HV < −20.5 dB; built-up HH > −3.5 or HV−HH < −10 or HV > −10.5; mangrove HV ≥ −19, HV−HH ≥ −8 and 100 m texture < 1.3 dB; other land is the rest. The thresholds were set by eye on the Rehri Goth sub-area (about 2% of the box); agreement is measured over the whole box. It exists to show that simple, explainable rules get most of the way, and that the AI does better.

### Forest watch (the trend)
For each mangrove pixel, HV in dB **minus the forest median of the same pass**, then a straight-line fit over the year:

> relative HV = a + b·time + m·(dual-pol pass) + c·tide

- **Forest mask:** GMW 2025, at least half the 20 m pixel (184.38 km²). It does not depend on the year being tested. (An earlier version used the AI map, which is built from the same year of data and could hide pixels that lost canopy early.)
- **Flag rule:** slope ≤ −1 dB/yr (weakening) or ≥ +1 dB/yr (strengthening), with |t| ≥ 2. The t value is deflated for autocorrelation between neighbouring passes (n_eff = n(1−r)/(1+r)).
- **What cancels:** anything that shifts the whole forest equally, such as calibration. A patch whose seasonal or tidal behaviour differs from the forest's still gets a slope.
- **Shuffle test:** the order of the passes is shuffled 20 times (the same shuffle for all pixels) and the fit repeated. Noise alone flags about 0.6% weakening and 0.7% strengthening, against 8.5% and 13.4% in the real data. So the pattern is real. The shuffle does not test season, because it also destroys any seasonal curve.

### Tide check
Predicted tide height at the 28 pass times ranges from −1.57 m to +0.99 m. Passes happen at the same clock time every 12 days, so they land at a different point in the spring–neap cycle each time (the pattern repeats about every 64 days).
- Tide is not linked to time over the year (correlation 0.03), so it cannot fake a trend by itself.
- The whole forest reads darker at higher tide (correlation of the forest median with tide: HV −0.46, HH −0.40, quad-pol passes).
- About 9% of forest pixels follow the tide strongly (|r| > 0.5).
- With tide in the fit, weakening is 8.5%; without it, 8.1%. None of the eight alerts follows the tide.
- Limit: a global model at one open-water point, not a gauge inside the creeks.

### Structural vs moisture change
Compares 3 quad-pol passes in Nov–Dec 2025 (21 Nov, 15 Dec, 27 Dec) with 3 in Aug–Oct 2026 (24 Aug, 17 Sep, 11 Oct), averaged and smoothed (60 m) in linear power. A pixel has *changed* if HV or HH moved by 2 dB or more. It is *structural* (canopy) if HV moved at least 1.5 dB more than HH; otherwise it is *moisture* (wetter or drier ground, flooding). Inside the forest almost nothing changed structurally (canopy loss 0.02%, gain 0.13%). The windows are not the same season, so moisture changes are expected.

### Alerts (`scripts/monitor/coastlens_monitor.py`)
1. **Entry condition:** 100 m cells where at least 40% of the mangrove pixels are weakening in the trend. Touching cells are joined into patches.
2. **Minimum size from the shuffle test:** the same pipeline is run on the 20 shuffled trend maps; the smallest patch size kept is the first where noise gives fewer than one alert on average. That is **1 ha** (0.65 chance alerts on average).
3. **Supporting records,** checked after a patch qualifies:
   - Long-term L-band record: a GMW decline zone, GMW loss 2015–2025 over at least 5% of the patch and 200 m around it, or an ALOS-2 drop of 2 dB or more (relative to the forest) in at least half the patch. GMW v4.1 is partly built from JAXA L-band radar, the same family as ALOS-2, so these count as **one** record, not two.
   - Landsat NDVI down by 0.1 or more since 2015–16, in at least 25% of the patch.
   - Sentinel-1 VH down by 2 dB or more since 2018 (relative to the forest), in at least 25%.
   - NISAR structural canopy loss in at least 10%.
4. **Which eight are shown:** the largest, at least 500 m apart. Size decides because size is what the shuffle test supports.
5. **Result:** 120 candidates; 99 have no supporting record, 21 have one, none has two. The eight shown have none.
6. **Base rates,** published in `alerts.json`: the long-term record is met by 15.3% of all forest cells and by 17.5% of candidates, so it does not single the candidates out. The feed also lists passes that have flown but are not yet published, and the next pass date.

### HH display
HH is about 7–10 dB brighter than HV, so it has its own grey scale (−20 to 0 dB; on 11 Oct 2026 the 2nd–98th percentiles are −19.6 to −1.8 dB). HV layers use −25 to −5 dB.

## 4. Questions you may be asked

**"Are the alerts mangrove loss?"**
No, and the site never says so. An alert means the radar signal of that patch weakened by about 1.5–1.7 dB per year relative to the rest of the forest. The cause could be cutting, browsing, burial or blocked channels, but also season or tide. That is why every alert says "not field-checked".

**"How do you know it isn't just noise?"**
We shuffled the order of the passes 20 times and ran the exact same pipeline. On average noise gives 0.65 alerts of 1 ha or more; the real data gives 120 candidates. Honest detail: in 17 of 20 shuffles noise gave none, but one shuffle gave eight small patches and another gave four, the largest 4.8 ha. Five of our alerts are over 9 ha, larger than anything noise produced; the smallest three (4.2–4.8 ha) are within the range noise reached once.

**"Isn't this just the season?"**
It could partly be. With less than one year of data, a straight line and a seasonal curve look alike, and no statistical trick separates them. The fix is to compare the same months a year apart: Nov–Dec 2025 against Nov–Dec 2026, quad-pol on both sides, once NISAR publishes those passes. The site says this.

**"Did you check the tide?"**
Yes. We added predicted tide height at every pass from NASA's GOT4.10 model as a term in the fit. It changes the weakening share only from 8.1% to 8.5%, and none of the eight alerts follows the tide. The forest as a whole does read darker at high tide, so the tide is real in the data; it just does not explain the alerts.

**"Why is more of the forest strengthening than weakening?"**
A measure relative to the forest itself should balance around zero. It does not (13.4% vs 8.5%), which suggests a shape effect such as edge pixels behaving differently through the year. We state it on the map as an open question.

**"Why did you mix data versions?"**
We avoided it where it matters. 26 of 27 passes are provisional; the last (23 Oct 2026) is validated. The trend works relative to each pass's own forest median, so a version shift that moves the whole pass cancels. The beta release of Nov 2025 reads about 3–5 dB darker than the reprocessed provisional file (most in mangrove), so we use only the provisional one. The December coherence pair is still a beta product, and the map says so.

**"How accurate is the AI map?"**
95.4% accurate on 2 km blocks it never saw, precision 91.3%, recall 96.6%, F1 0.94, on pixels where GMW is sure. Mixed edge pixels are not in that test. It is checked against GMW, so it cannot be better than GMW.

**"Why three different mangrove areas for 2025?"**
180.9 km² is GMW on its own grid inside the lat/lon box. 184.36 km² is the same GMW map moved onto the NISAR 20 m grid, which is a slightly larger rectangle. 194.48 km² is our AI map, which also includes some edge pixels.

**"Why L-band and not C-band?"**
L-band waves (about 24 cm) pass through leaves and bounce off trunks and branches, so they measure woody structure. C-band (about 5.6 cm, Sentinel-1) mostly sees the top of the canopy. On the same pixels, Sentinel-1 VH separates mangrove with AUC 0.918; our NISAR model reaches 0.992. Optical NDVI is also very good (0.991) but needs clear sky.

**"Is 'about a year before optical' solid?"**
In zone C, relative to stable reference forest, the ALOS-2 signal first dropped clearly in the 2017 mosaic (about −3 dB). Landsat NDVI dropped in the 2018 dry season (Nov 2017 – Feb 2018). Because the ALOS-2 mosaic is one picture per year, the lead is at most about a year and could be only months. The 2016 drop is not counted: the reference forest dropped by almost the same amount that year, so it was a shift of the whole mosaic.

**"How much of the gain was planted?"**
We do not know for this box. Ahmed et al. (2025) report large rehabilitation across the Indus Delta; we cite that and say the planted share here is not measured. Planting records are one of the things we ask collaborators for.

**"What about S-band?"**
NISAR also carries ISRO's S-band radar, but ASF lists only L-band files over our box. The S-band view on the site is a labelled concept, not data.

## 5. Known limits

- One year of NISAR: trend and season cannot yet be separated.
- No field checks yet; every alert is a lead.
- Tide comes from a global model, not a local gauge.
- The AI map is trained and tested against GMW, so it shares GMW's errors.
- Rule thresholds were set by eye on a small sub-area.
- The December 2025 coherence pair is a beta product.
- The 80 m NISAR time-series charts on the Insights page average both imaging modes.

## 6. How it was built

### Website
- **Static site built with Vite 6**, plain JavaScript (no framework). Libraries: **Leaflet** (maps), **GSAP** (scroll animation), **Lenis** (smooth scrolling). Radar animations and clouds are drawn on canvas by our own code and labelled as illustrations.
- **3D models** are shown through the Sketchfab Viewer API, with our own info dots pinned to points on each model: the home page red mangrove ("red-mangrove-tree" by SAVIA_Colombia, CC BY 4.0) and the NISAR page satellite (by MechLab3D). The fish journey and card images are generated illustrations in `public/media/`.
- **Hosting:** Vercel. Build command `npm run build`, output `dist/`. The Python pipeline and raw data are not deployed (`.vercelignore`).
- **Map tiles** are self-hosted in `public/tiles/<layer-id>/{z}/{x}/{y}.png` (zoom 10–14, Sentinel-2 to 15), cut by `scripts/tiles/make_tiles.py`.
- **No number is typed into the page by hand.** Charts, story texts and alert texts read `stats.json` and `alerts.json`. Layer descriptions in `layers.json` write numbers as `{{path.in.stats.json}}`, which the map page fills in when it loads.

### Data pipeline (Python, in `scripts/`)

```
ASF (NISAR GCOV, GUNW) --remote_h5.py: read only our box--> nisar_pixel_stack.py --> 20 m stack (27 passes)
                                                                                      |
Global Mangrove Watch v4.1 --> gmw_timeseries.py, gmw_v4_layers.py, gmw_decline_zones.py   |
Earth Engine (Landsat, Sentinel-1/2, ALOS) --> export_layers.py, older_sensors.py          |
GOT4.10 tide model --> tide_at_pass.py --> docs/tide_at_pass.csv                           |
                                                                                      v
                       nisar_pixel_products.py: AI map, land cover, trend + shuffle test,
                       structural vs moisture, mode offsets, zone status --> stats.json
                                                                                      |
                       coastlens_monitor.py: alerts --> alerts.json, places.geojson, docs/alerts/latest.md
                                                                                      |
                       make_tiles.py: coloured GeoTIFF --> public/tiles/  -->  the website
```

Main Python libraries: numpy, rasterio (GDAL), h5py, scikit-learn, shapely, pyproj, mercantile, Pillow, earthengine-api, asf_search, keyring (stores the Earthdata token in Windows Credential Manager, never in code), pyTMD (tide). Full commands are in [`scripts/README.md`](scripts/README.md).

### Order of work
1. Chose the study box and pulled 40 years of mangrove history from GMW v4.1; found the seven decline zones.
2. Exported optical and older radar layers from Google Earth Engine.
3. Found every NISAR pass over the box on ASF and wrote a reader that streams only our box from each 6 GB file.
4. Built the per-pixel stack, the AI map, the trend, the change-type map and the alerts; cut everything into tiles.
5. Built the six-page site and deployed it on Vercel (14–15 Nov 2026).
6. **Review and corrections (15 Nov 2026).** An independent review of the live map and the code (`docs/CoastLens_Map_Problems.pdf`, `docs/MAP_FIX_GUIDE.md`) found 21 problems, mostly wording that claimed more than the data showed. All were addressed:
   - Wording: "mangrove thinning", "statistically significant", "independent signals", "High priority", "keeps dying" and "two years before optical" were replaced with what the data supports.
   - Method: the imaging-mode offset was measured and handled; the trend got an independent forest mask, a shuffle test, an autocorrelation correction and a tide term; the alert rules were rebuilt with merged L-band records, an optical record, base rates and a chance-expected count; three dB averages were moved to linear power.
   - Display: HH got its own colour range; all change layers use red/blue; the alert popup and legend were fixed for phones.
   - Still open: the same-season comparison, which needs the Nov–Dec 2026 passes.

### Updating after each NISAR pass

```bash
python scripts/monitor/coastlens_monitor.py   # finds new passes on ASF, rebuilds products and alerts
python scripts/nisar/tide_at_pass.py          # adds tide for the new passes
# then re-cut tiles for layers that changed (see scripts/README.md) and redeploy
```

## 7. Developer notes

### Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # output in dist/
```

Deploy on Vercel: import the repo, framework preset **Vite**. No other settings.

### Where things are

| What | File |
|---|---|
| Colours, type, spacing | top of `src/styles.css` (`:root`) |
| Nav, footer, smooth scroll, reveals, cursor, the Finding component | `src/core.js` |
| Home page sections | `index.html` + `src/home.js` |
| NISAR explainer animations | `nisar.html` + `src/nisar.js` |
| Findings, charts, compare map, NISAR alerts | `insights.html` + `src/insights.js` |
| Full map: every layer, decline zones, alerts, stories | `map.html` + `src/map.js` (layers from `public/data/layers.json`) |
| 3D mangrove on Home (Sketchfab) | `src/mangrove3d.js` |
| Radar tree on NISAR page | `src/tree3d.js` |
| Home page images (fish journey, cards, satellite) | `public/media/` |
| Home page impact map | `#impactMap` in `index.html`, bottom of `src/home.js` |
| Real imagery loader | `src/tiles.js` |
| Every number on the site | `public/data/stats.json` |
| Map layers, decline zones, alerts | `public/data/layers.json`, `zones.geojson`, `alerts.json`; tiles in `public/tiles/` |
| Data pipeline | `scripts/` (see `scripts/README.md`) |
| Sources for every figure | `SOURCES.md`, `docs/resources-used.md` |
| Team and collaborators | `about.html`, `collaborators.html` (search for `TEAM:` and `COLLABORATORS:`) |

### Rules the site follows

- Green only for mangroves and vegetation. Pink only for loss and warnings. Red/blue for decrease/increase on change layers.
- Every finding uses `finding()` from `src/core.js`: measured, possible explanation, confidence.
- Alerts say "radar signal weakening", never "thinning" or "loss", until someone has checked on the ground.
- Clouds and the tree are illustrations and are labelled as such. S-band is a labelled concept: there is no S-band data.
- Motion respects `prefers-reduced-motion`.
- Raw data (`data_raw/`) and Python environments are not in git; `scripts/README.md` explains how to regenerate them.
