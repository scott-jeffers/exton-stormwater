# Brandywine Creek HEC-RAS 2D models (Chester County, PA)

> **Draft, under calibration (Nov 2026).** These are planning and screening models, not regulatory flood maps.

This folder holds linked HEC-RAS 7.0.1 rain-on-grid models of the Brandywine Creek watershed above Chadds Ford. They are shared openly so anyone can download them, run them and review the work.

- **Results and maps:** [Brandywine planning site](https://scott-jeffers.github.io/exton-stormwater/County/#brandywine) and the [Brandywine Flood Watch dashboard](https://scott-jeffers.github.io/exton-stormwater/Brandywine/).
- **Readable files (this folder):** the project, geometry, plan and flow text files for every model, plus the scripts used to build, link and run them. You can read these in the browser.
- **Ready-to-run downloads:** each model packaged as one zip on the [release page](https://github.com/scott-jeffers/exton-stormwater/releases/tag/brandywine-models-v0.9). Each zip includes the terrain, land cover, soils, geometry HDF and all plans.

## The models

Models are linked from upstream to downstream. Each upstream model's outlet hydrograph is the inflow boundary of the next model down.

```
M03 Upper East Branch & Marsh Creek ─┐
M01 Valley Creek (Exton) ────────────┴─> M02 East Branch – Downingtown ─┐
M12 Buck Run & Doe Run ──────────────> M04 West Branch – Coatesville ───┴─> M05 Main stem – Chadds Ford
```

| ID | Model | Download | Area (sq mi) | 2D cells | Inflows from |
|---|---|---|---|---|---|
| M03 | Upper East Branch & Marsh Creek | `M03_UpperEastBranch_MarshCreek.zip` (936 MB) | 60.0 | 279k | none |
| M01 | Valley Creek, Exton (built earlier; files in [`/Model`](../Model)) | `M01_ValleyCreek.zip` (278 MB) | 20.7 | 171k | none |
| M02 | East Branch – Downingtown | `M02_Downingtown.zip` (469 MB) | 42.1 | 199k | M03, M01 |
| M12 | Buck Run & Doe Run | `M12_BuckDoeRun.zip` (522 MB) | 48.5 | 229k | none |
| M04 | West Branch – Coatesville | `M04_WestBranch_Coatesville.zip` (931 MB) | 86.0 | 407k | M12 |
| M05 | Brandywine main stem – Chadds Ford | `M05_BrandywineMain.zip` (377 MB) | 34.3 | 163k | M02, M04 |
| S01 | Scenario: Mary Street wetland, Downingtown (100-yr) | `S01_Downingtown_MaryStWetland.zip` (396 MB) | – | – | M03, M01 |

SHA-256 checksums are in [`SHA256SUMS.txt`](SHA256SUMS.txt).

## Plans in each model

| Plan | Storm | Notes |
|---|---|---|
| p01–p05 | 2, 5, 10, 25, 100-yr 6-hr (Atlas 14, SCS Type II) | p03 (10-yr 6-hr) is the standard test run |
| p06–p11 | 24-hr warm-up runs (0–3 h) | Earlier restart approach; p12–p17 no longer need them |
| p12–p17 | 2, 5, 10, 25, 50, 100-yr 24-hr (Atlas 14, SCS Type II) | 36-hour window, cold start |
| p18 | Hurricane Ida (Sept 1, 2021), uniform rain from gauge totals | Superseded by p19 |
| p19 | Hurricane Ida, gridded NOAA MRMS radar rain (hourly, 1,000 ft grid) | M03, M12 and M02 only, so far |

## How to run a model

1. Install [HEC-RAS 7.0.1](https://www.hec.usace.army.mil/software/hec-ras/download.aspx) (Windows).
2. Download a zip from the release page and unzip it anywhere. Keep the folder structure.
3. Open the `.prj` in HEC-RAS. Choose a plan (Run > Unsteady Flow Analysis), keep *Geometry Preprocessor* checked, and click Compute.
   - HEC-RAS rebuilds its geometry tables on the first run, which can take a few minutes.
   - A 24-hr storm takes about 2–4 hours on a 4-core PC.
4. View results in RAS Mapper.

**Linked inflows.** The inflow boundaries (for example `M03_Inflow` in M02) hold hydrographs copied from the upstream model's results for the same storm. If you change an upstream model, rerun it and refill the downstream inflow. `scripts/radar_and_linking/fill_u.py` does this from a 5-minute outlet series. Inflows that haven't been filled yet are flat. At the time of this release:
- the M04 Coatesville 100-yr and 10-yr inflows are filled;
- the M05 main-stem 24-hr inflows are still flat (pending).

## Calibration status (Hurricane Ida, Sept 1, 2021)

| Check | Measured | Model |
|---|---|---|
| USGS 01480700 East Branch at Dowlin Forge, peak flow | 16,100 cfs at 7:37 pm | 8,258 cfs (radar rain, normal soil) → **13,984 cfs at 8:00 pm** (radar rain incl. morning rain, wet soil AMC III) |
| High-water mark at Dowlin Forge Rd | 270.8 ft | 266.8 ft → **269.9 ft** (wet soil) |

The radar rain matches the rain gauges within 1–2% over the upper East Branch. Most of the remaining gap came from the soil being wetter than normal. Rain earlier that day left little room for infiltration. The wet-soil (AMC III) versions are being run for the other models now and will be added to the next release.

Design-storm peaks are being checked against log-Pearson III fits of the USGS annual peaks. See the planning site for the current comparison.

## Data sources

- **Terrain:** USGS 3DEP 1 m lidar (PA), with culverts and bridge openings burned in and flood-control dam embankments restored.
- **Land cover and imperviousness:** Chester County / DVRPC land use and impervious-surface layers. Areas outside Chester County default to meadow.
- **Soils:** NRCS SSURGO hydrologic soil groups, SCS curve-number infiltration.
- **Design rain:** NOAA Atlas 14, Volume 2. **Ida rain:** NOAA MRMS MultiSensor QPE Pass 2, 1-hour ([AWS open data](https://registry.opendata.aws/noaa-mrms-pds/)).
- **Storm sewers:** Chester County and municipal MS4 mapping; many sizes and depths inferred.
- **Dams:** Beaver Creek, Hibernia, Barneston, Marsh Creek and Wharton Blvd are modeled as SA/2D connections. Several outlet details are assumed; see `scripts/model_setup/dams_final/dams.json`.
- **Gauges:** USGS annual peaks and Ida records; rain-gauge storm totals for the radar check.

## Scripts

| Folder | What it does |
|---|---|
| `scripts/watershed_build` | Steps 1–9: DEMs, subwatersheds, culvert burning, land cover and soils, meshes, and writing the HEC-RAS files |
| `scripts/model_setup` | Dam connections, the Hibernia fix, boundary offsets, plan setup, outflow extraction and packaging |
| `scripts/radar_and_linking` | MRMS radar gridding (ras-commander), plan creation, inflow filling, NEER cloud runs, result extraction |

The scripts still point at the folders where they were written (for example `/home/claude/ebb/...`). Change those paths for your own setup. The NEER script reads your own key from the `NEER_API_KEY` environment variable.

## Known limitations

- Storm-sewer sizes are partly inferred, and several dam outlets are assumed. Get as-builts from CCWRA or DCNR to replace them.
- The 2D-only approach smooths the channel in places, and bridges are represented as terrain openings rather than full bridge structures.
- Not reviewed by FEMA, PA DEP or CCWRA. Use with judgment and follow official NWS warnings in an emergency.

## Feedback

Questions and corrections are welcome. Please open an [issue](https://github.com/scott-jeffers/exton-stormwater/issues) on this repository.
