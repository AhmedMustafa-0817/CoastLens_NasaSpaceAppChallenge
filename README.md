# CoastLens

Scroll-driven site for the NASA Space Apps Challenge 2026 ("Dancing with the SARs").
Five pages: Home, NISAR, Insights, Collaborators, About us.

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
| Findings, charts, compare map | `insights.html` + `src/insights.js` |
| 3D mangrove (home and NISAR) | `src/tree3d.js` |
| Real imagery loader | `src/tiles.js` |
| Every number on the site | `public/data/stats.json` |
| Team and collaborators | `about.html`, `collaborators.html` (search for `TEAM:` and `COLLABORATORS:`) |

## Updating data

- **Numbers and charts:** replace `public/data/stats.json` (same shape as the analysis site's file, plus a `flags` array taken from `places.geojson`). Finding text on Insights is built from these values.
- **Map and hero imagery:** tiles load from the analysis site. Change `TILE_BASE` in `src/tiles.js` if they move. To self-host, copy the `tiles/` folder into `public/` and set `TILE_BASE = '/tiles'`.
- **Layers in the compare map:** edit the `LAYERS` list in `src/insights.js`.
- **Hero / reveal layers:** `OPTICAL` and `RADAR` at the top of `src/home.js`.

## Rules the site follows

- Green is only used for mangroves. Pink is only used for loss and warnings. L-band and S-band each keep one colour.
- Every finding uses `finding()` from `src/core.js`: measured, possible explanation, confidence.
- Clouds and the tree are illustrations and are labelled as such. S-band is a labelled concept: there is no S-band data.
- Motion respects `prefers-reduced-motion`.
- Sources for every figure: `SOURCES.md`.
