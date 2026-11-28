# Brandywine Flood Watch: dashboard

A static web page with no build step. Open `index.html` directly, or host the folder on any static web host. GitHub Pages serves it from the `main` branch.

## What it shows
- **Rain:** what has fallen (NOAA MRMS), and the NWS forecast for the next 6 hr, 1 day, 3 days, 5 days and 7 days. Each total is compared to a NOAA Atlas 14 design storm ("about a 10-year storm"). The forecast map layer also offers 2 days.
- **Radar:** current radar and a 50-minute loop, both off by default.
- **Alerts:** NWS warning areas.
- **Gauges:**
  - one marker per site, with live USGS stage and flow, the last 2 days, and a USGS link;
  - where NWS forecasts the site, the NOAA hydrograph and a link to the NOAA gauge viewer.
- **Flood map:** HEC-RAS maximum depth for the design storm picked in the dropdown. The automatic match picks the modeled storm closest to the NWS rain forecast, once that forecast reaches about a 2-year storm.
- **Critical only / Everything:** thresholds that control which roads, crossings and buildings are flagged.

| | Critical only | Everything |
|---|---|---|
| Roads | 2 ft+ of water over 150 ft+ (evacuation and major roads: 1 ft+ over 50 ft+) | 1 ft+ over 50 ft+ |
| Crossings under a mapped road | 1 ft+ over the road | ½ ft+ |
| Buildings | 3 ft+ of water alongside | 1½ ft+ |
| Shaded depth | 1 ft+ | ½ ft+ |

- **FEMA flood zones:** the effective NFHL zones, embedded in the page.
- **Model layers:** storm sewers, outfalls, road crossings, the watershed and streams.
- **Exports:** a GeoJSON for SARTopo / CalTopo and a CSV of roads to close.
- **Defaults:** imagery background map, legend collapsed.

## Brandywine notes
- Five linked HEC-RAS 2D models (Upper East Branch, Buck/Doe Run, Downingtown, Coatesville, main stem). Scenarios merge the models that have finished each storm; `meta.models` in each scenario file lists them.
- FEMA zones are drawn live from FEMA's NFHL map service, not embedded.
- Storm sewers are not modeled. Road flags come from a 30-ft depth grid on bare-earth lidar; runs that sit 8 ft+ below the road on both sides (bridge spans) are dropped.
- Built by `floodwatch_export.py` in the model workspace.

## Data
- `data/model_layers.js`: watershed, streams, crossings, pipes, outfalls, municipalities and Atlas 14 values.
- `data/fema_zones.js`: FEMA flood zones.
- `data/scenarios/`: one file per HEC-RAS run, plus the catalog in `index.js`.

## Updating
The scripts in `tools/` export a run and rebuild the catalog:

- `export_scenario.py <plan.hdf> <id> "<name>"`
- `build_index.py`

They were written for the Linux workspace used to build the model, so edit the folder paths at the top of each one before using them elsewhere.
