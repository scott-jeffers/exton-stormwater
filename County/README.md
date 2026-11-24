# Chester County Flood Program dashboard

Live page: https://scott-jeffers.github.io/exton-stormwater/County/

Plain HTML + Leaflet, no build step. Open `index.html` through any web server (or GitHub Pages) to view.

| File | What it is | Edit it to |
|---|---|---|
| `data/program.json` | Status, phase, towns, notes and dashboard link for each of the 16 models | Move a model to "In progress" or "Modeled", change phases, add notes |
| `data/models.geojson` | Outline of each planned model (HUC-12s grouped) | Regroup watersheds (rebuild with the script in the NEER project notes) |
| `data/watersheds.geojson` | The 46 HUC-12 watersheds in the county, clipped to the county line | Rarely |
| `data/usgs_gauges.geojson`, `data/noaa_gauges.geojson` | Gauge locations; readings load live from USGS and NOAA when a gauge is clicked | Add or remove gauges |
| `index.html` | The page; phase colours are the CSS variables at the top | Change look and layout |

Status values: `Modeled`, `In progress`, `Pilot - next`, `Planned`. Phase: `0` done, `1`–`4` planned phase.
