# CoastLens

Scroll-driven site for the NASA Space Apps Challenge 2026 ("Dancing with the SARs").
Six pages: Home, NISAR, Insights, Map, Collaborators, About us. The data pipeline that makes every number and map layer lives in `scripts/` (Python).

## Run

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # output in dist/
```

Deploy on Vercel: import the repo, framework preset **Vite**. No other settings.

## Where things are

| What | File |
|---|---|
| Colours, type, spacing | top of `src/styles.css` (`:root`) |
| Nav, footer, smooth scroll, reveals, cursor, the Finding component | `src/core.js` |
| Home page sections | `index.html` + `src/home.js` |
| NISAR explainer animations | `nisar.html` + `src/nisar.js` |
| Findings, charts, compare map, NISAR alerts | `insights.html` + `src/insights.js` |
| Full map: every layer, decline zones, alerts | `map.html` + `src/map.js` (layers from `public/data/layers.json`) |
| 3D mangrove (home and NISAR) | `src/tree3d.js` |
| Real imagery loader | `src/tiles.js` |
| Every number on the site | `public/data/stats.json` |
| Map layers, decline zones, alerts | `public/data/layers.json`, `zones.geojson`, `alerts.json`; tiles in `public/tiles/` |
| Data pipeline (NISAR, GMW, Earth Engine, AI model, NGO monitor) | `scripts/` (see `scripts/README.md`) |
| Team and collaborators | `about.html`, `collaborators.html` (search for `TEAM:` and `COLLABORATORS:`) |

## Updating data

- **Numbers and charts:** the scripts in `scripts/` write `public/data/stats.json` directly. Finding text on Insights is built from these values.
- **Alerts:** after each NISAR pass (every 12 days) run `python scripts/monitor/coastlens_monitor.py`; it updates `public/data/alerts.json` and `places.geojson`.
- **Map and hero imagery:** tiles are self-hosted in `public/tiles/` (made by `scripts/tiles/make_tiles.py`). `TILE_BASE` in `src/tiles.js` points there.
- **Raw data** (`data_raw/`) and Python environments are not in git; `scripts/README.md` explains how to regenerate them.
- **Layers in the compare map:** edit the `LAYERS` list in `src/insights.js`. The full map reads every `ready` layer from `public/data/layers.json`.
- **Hero / reveal layers:** `OPTICAL` and `RADAR` at the top of `src/home.js`.

## Rules the site follows

- Green is only used for mangroves. Pink is only used for loss and warnings. L-band and S-band each keep one colour.
- Every finding uses `finding()` from `src/core.js`: measured, possible explanation, confidence.
- Clouds and the tree are illustrations and are labelled as such. S-band is a labelled concept: there is no S-band data.
- Motion respects `prefers-reduced-motion`.
- Sources for every figure: `SOURCES.md`.
