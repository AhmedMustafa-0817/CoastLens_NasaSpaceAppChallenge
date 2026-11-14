// =============================================================================
// CoastLens: export finished map layers + statistics from Google Earth Engine
// -----------------------------------------------------------------------------
// HOW TO USE
//   1. Paste this file into the Earth Engine Code Editor (code.earthengine.google.com).
//   2. Click Run. Every export appears in the Tasks tab, so click RUN on the ones you need.
//      Files land in Google Drive folder DRIVE_FOLDER as <layer-id>.tif
//   3. The Console prints a STATS JSON block. Copy it into public/data/stats.json.
//   4. Turn each .tif into web tiles:  python scripts/tiles/make_tiles.py <id>.tif public/tiles/<id>
//   5. In public/data/layers.json set that layer's "status" to "ready".
//
// Each export's name == the layer "id" in public/data/layers.json. Keep them in sync.
// Exports are already colourised RGB + alpha (uint8), ready to tile. They are for DISPLAY.
// Do analysis on the raw images inside Earth Engine, not on these PNG-ready files.
// =============================================================================

// ---------- 1. Settings ----------
var AOI = ee.Geometry.Rectangle([67.155304, 24.671376, 67.433395, 24.828817]); // Karachi mangrove coast study area (Rehri Goth to Port Qasim), team box 2026-11-14
var DRIVE_FOLDER = 'coastlens_exports';
var EXPORT_CRS = 'EPSG:3857'; // web-map projection, so tiling needs no extra warping

// Dry-season windows (Nov–Feb). End dates are exclusive.
var SEASONS = {
  '2015_16': ['2015-11-01', '2016-03-01'],
  '2017_18': ['2017-11-01', '2018-03-01'],
  '2018_19': ['2018-11-01', '2019-03-01'],
  '2021_22': ['2021-11-01', '2022-03-01'],
  '2024_25': ['2024-11-01', '2025-03-01'],
  '2025_26': ['2025-11-01', '2026-03-01']
};

// Sentinel-1: use ONE orbit direction so all composites share the same viewing
// geometry. Check the printed counts and switch to 'ASCENDING' if that has more scenes.
var S1_PASS = 'DESCENDING';

Map.centerObject(AOI, 10);
Map.addLayer(AOI, {color: 'yellow'}, 'AOI', true, 0.3);

// ---------- 2. Image builders (cloud-masked, clipped to AOI) ----------
function maskLandsat(img) {
  var qa = img.select('QA_PIXEL');
  var clear = qa.bitwiseAnd(1 << 1).eq(0)       // dilated cloud
    .and(qa.bitwiseAnd(1 << 3).eq(0))           // cloud
    .and(qa.bitwiseAnd(1 << 4).eq(0));          // cloud shadow
  return img.updateMask(clear)
    .select(['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6'], ['blue', 'green', 'red', 'nir', 'swir1'])
    .multiply(0.0000275).add(-0.2);
}
function landsat8(season) {
  var r = SEASONS[season];
  var col = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(AOI).filterDate(r[0], r[1]);
  print('Landsat 8 scenes ' + season, col.size());
  return col.map(maskLandsat).median().clip(AOI);
}

var CLOUD_SCORE = ee.ImageCollection('GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED');
function sentinel2(season) {
  var r = SEASONS[season];
  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(AOI).filterDate(r[0], r[1]);
  print('Sentinel-2 scenes ' + season, col.size());
  return col.linkCollection(CLOUD_SCORE, ['cs_cdf'])
    .map(function (img) {
      return img.updateMask(img.select('cs_cdf').gte(0.6))
        .select(['B2', 'B3', 'B4', 'B8', 'B11'], ['blue', 'green', 'red', 'nir', 'swir1'])
        .divide(10000);
    })
    .median().clip(AOI);
}

function sentinel1VH(season) {
  var r = SEASONS[season];
  var col = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(AOI).filterDate(r[0], r[1])
    .filter(ee.Filter.eq('instrumentMode', 'IW'))
    .filter(ee.Filter.eq('orbitProperties_pass', S1_PASS))
    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
    .select('VH');
  print('Sentinel-1 ' + S1_PASS + ' scenes ' + season, col.size());
  // Light speckle reduction (values are already in dB in this collection).
  return col.map(function (img) { return img.focalMedian(30, 'circle', 'meters'); }).median().clip(AOI);
}

function ndvi(img) { return img.normalizedDifference(['nir', 'red']).rename('ndvi'); }

var GMW = 'projects/earthengine-legacy/assets/projects/sat-io/open-datasets/GMW/extent/';
function mangrove(year) {
  var vectors = ee.FeatureCollection(GMW + 'gmw_v3_' + year + '_vec').filterBounds(AOI);
  return ee.Image(0).byte().paint(vectors, 1).clip(AOI).rename('mangrove');
}

// ---------- 3. Display styles (must match legends in layers.json) ----------
var STYLE = {
  truecolor: {bands: ['red', 'green', 'blue'], min: 0, max: 0.25},
  ndvi: {min: 0, max: 0.8, palette: ['8b4513', 'ffff00', '008000']},
  ndviChange: {min: -0.4, max: 0.4, palette: ['ff0000', 'ffffff', '008000']},
  s1: {min: -25, max: -5, palette: ['000000', 'ffffff']},
  mangrove: {min: 1, max: 1, palette: ['00aa00']},
  lossGain: {min: 1, max: 2, palette: ['e63946', '1d6fe0']}
};

// RGB + alpha (uint8). Masked pixels get alpha 0 so they are transparent on the web map.
function rgba(img, vis) {
  var v = img.visualize(vis);
  var alpha = v.mask().reduce(ee.Reducer.min()).multiply(255).rename('alpha');
  return v.addBands(alpha).unmask(0).toUint8();
}

function exportLayer(id, image, vis, scale) {
  Map.addLayer(image, vis, id, false);
  Export.image.toDrive({
    image: rgba(image, vis),
    description: id,
    folder: DRIVE_FOLDER,
    fileNamePrefix: id,
    region: AOI,
    scale: scale,
    crs: EXPORT_CRS,
    maxPixels: 1e10
  });
}

// ---------- 4. Layer exports ----------
var L8 = {};
['2015_16', '2018_19', '2021_22', '2024_25'].forEach(function (s) {
  L8[s] = landsat8(s);
  exportLayer('l8_truecolor_' + s, L8[s], STYLE.truecolor, 30);
});
exportLayer('l8_ndvi_2015_16', ndvi(L8['2015_16']), STYLE.ndvi, 30);
exportLayer('l8_ndvi_2024_25', ndvi(L8['2024_25']), STYLE.ndvi, 30);
exportLayer('l8_ndvi_change_2015_16_to_2024_25',
  ndvi(L8['2024_25']).subtract(ndvi(L8['2015_16'])), STYLE.ndviChange, 30);

exportLayer('s2_truecolor_2018_19', sentinel2('2018_19'), STYLE.truecolor, 10);
exportLayer('s2_truecolor_2025_26', sentinel2('2025_26'), STYLE.truecolor, 10);

var S1 = {'2017_18': sentinel1VH('2017_18'), '2025_26': sentinel1VH('2025_26')};
exportLayer('s1_vh_2017_18', S1['2017_18'], STYLE.s1, 20);
exportLayer('s1_vh_2025_26', S1['2025_26'], STYLE.s1, 20);

var m1996 = mangrove(1996);
var m2020 = mangrove(2020);
var loss = m1996.eq(1).and(m2020.eq(0));
var gain = m1996.eq(0).and(m2020.eq(1));
var stable = m1996.eq(1).and(m2020.eq(1));
exportLayer('gmw_1996', m1996.selfMask(), STYLE.mangrove, 25);
exportLayer('gmw_2020', m2020.selfMask(), STYLE.mangrove, 25);
exportLayer('gmw_lossgain_1996_2020', loss.add(gain.multiply(2)).selfMask(), STYLE.lossGain, 25);

// ---------- 5. STATS -> public/data/stats.json ----------
function areaKm2(mask) {
  return ee.Image.pixelArea().divide(1e6).updateMask(mask).reduceRegion({
    reducer: ee.Reducer.sum(), geometry: AOI, scale: 25, maxPixels: 1e10
  }).values().get(0);
}
function meanIn(img, mask, scale) {
  return img.updateMask(mask).reduceRegion({
    reducer: ee.Reducer.mean(), geometry: AOI, scale: scale, maxPixels: 1e10
  }).values().get(0);
}

var GMW_YEARS = [1996, 2007, 2010, 2020];
var ndviSeasons = ['2015_16', '2018_19', '2021_22', '2024_25'];
var mangroveMask2020 = m2020.eq(1);

ee.Dictionary({
  area: ee.List(GMW_YEARS.map(function (y) { return areaKm2(mangrove(y).eq(1)); })),
  gain: areaKm2(gain),
  loss: areaKm2(loss),
  stable: areaKm2(stable),
  ndvi: ee.List(ndviSeasons.map(function (s) { return meanIn(ndvi(L8[s]), mangroveMask2020, 30); })),
  s1: ee.List(['2017_18', '2025_26'].map(function (s) { return meanIn(S1[s], mangroveMask2020, 20); }))
}).evaluate(function (d, err) {
  if (err) { print('STATS ERROR', err); return; }
  var stats = {
    status: 'ready',
    generated: new Date().toISOString().slice(0, 10),
    aoi: 'Karachi mangrove coast, Rehri Goth to Port Qasim (67.155304–67.433395E, 24.671376–24.828817N, about 28 x 17.5 km)',
    mangrove_area: {
      source: 'Global Mangrove Watch v3 extent, area computed by CoastLens within the AOI (25 m)',
      unit: 'km2',
      years: GMW_YEARS.map(function (y, i) { return {year: y, km2: d.area[i]}; })
    },
    mangrove_change: {
      from: 1996, to: 2020,
      source: 'Global Mangrove Watch v3, 1996 vs 2020 (map differencing; includes mapping error)',
      gain_km2: d.gain, loss_km2: d.loss, stable_km2: d.stable
    },
    ndvi_in_mangroves: {
      source: 'Landsat 8 C2 L2, Nov–Feb cloud-masked median; mean NDVI inside GMW 2020 mangrove extent',
      series: ndviSeasons.map(function (s, i) { return {season: s.replace('_', '–'), mean: d.ndvi[i]}; })
    },
    s1_vh_in_mangroves: {
      source: 'Sentinel-1 GRD VH (' + S1_PASS + '), Nov–Feb median; mean dB inside GMW 2020 mangrove extent',
      series: ['2017_18', '2025_26'].map(function (s, i) { return {season: s.replace('_', '–'), mean_db: d.s1[i]}; })
    },
    nisar: null
  };
  print('===== STATS: copy everything below into public/data/stats.json =====');
  print(JSON.stringify(stats, null, 2));
});
