# Valley Creek (Exton, PA) stormwater flood model and dashboard

This repository holds a HEC-RAS 7 1D/2D rain-on-grid flood model and a public flood-watch dashboard for the 20.8 sq mi Valley Creek watershed in Exton / West Whiteland, Chester County, PA.

- **`Dashboard/`**: a static web page showing radar, past and forecast rain (6 hr to 7 days), NWS alerts, live USGS / NOAA gauges, FEMA flood zones and modeled flood depths for the design storms. Live page: https://scott-jeffers.github.io/exton-stormwater/ (GitHub Pages, served from `main`).
- **`Model/`**: the HEC-RAS project text files (project, geometry with the storm-sewer network, flow and plan files). The large HDF results and the terrain are not stored here.
- **`Scripts/`**: Python scripts that built the terrain, culverts, pipe network, mesh, land cover and soils, and the design-storm plans.
- **`GIS/`**: Atlas 14 SCS Type II design-storm hyetographs and the inferred-culvert table.

## Model
| Item | Details |
|---|---|
| Terrain | USGS 1 m lidar with inferred culverts and bridges burned in |
| 2D mesh | About 171,000 cells |
| Storm sewers | 2,383 pipes coupled to the 2D mesh |
| Land cover and soils | DVRPC land use and NRCS soils (SCS curve-number infiltration) |
| Design storms | NOAA Atlas 14, SCS Type II: 2, 5, 10, 25, 50 and 100-year at 6-hour and 24-hour durations |

The 24-hour storms start with a 3-hour warm-up run with small pipe time steps, then restart with larger steps. This avoids an instability in nearly empty pipes during the early drizzle.

## Disclaimer
These are planning and screening results.
- Many pipe and culvert sizes and depths were estimated, not surveyed.
- These are not regulatory flood maps. Follow official National Weather Service warnings and emergency management instructions.
