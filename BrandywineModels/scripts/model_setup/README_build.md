# East Branch Brandywine models - build steps

Scripts (in Scripts/build) run in order, same recipe as the Exton/Valley Creek model:

| Step | Script | What it does |
|---|---|---|
| 1 | s01_dem10.py | 10-ft DEM over both watersheds from USGS 1 m lidar (PA_17County_D24, 2024) |
| 2 | s02_delin.py | Flow direction (streams burned 2 ft), watershed above USGS 01480700 + 300 ft |
| 3 | s03_dem1m.py | 1 m terrain (EPSG:2272, US ft) clipped to watershed + 600 ft |
| 4 | s04_culverts.py | Road embankments blocking streams -> culverts sized for Atlas 14 10-yr; DA >= 1 sq mi -> bridges |
| 5 | s05_burn.py | Notch bridges, burn culverts into terrain (excluded on Upper EB: C0001-3, C0031, C0109, C0140 = lake-shore artifacts) |
| - | (inline) | Marsh Creek Lake raised to normal pool 359.1 ft NAVD88 (lidar caught it drawn down to 354.4) |
| 5b | s09_crosscheck.py | Cross-check against PennDOT BMS2 structures and county road-crossing pipes (log: crosscheck_log.csv) |
| 5c | s05b_burn_final.py | Burn the cross-checked set into the original DEM and set Marsh Creek Lake to normal pool |
| 6 | s06_lcsoil.py | Land cover (DVRPC 2015 + county impervious), SSURGO soils, SCS CN infiltration (Exton tables) |
| 7 | s07_mesh.py | Perimeter, outlet BC line (normal depth), mesh points: 80 ft base, 40 ft along streams >= 300 ac |
| 8 | s08_gen_ras.py | HEC-RAS 7.0.1 project: 6-hr storms p01-p05, 24-hr warm-ups p06-p11, 24-hr storms p12-p17 (restart at 03:00) |

Marsh Creek Dam (F. Houston McIlvain Dam, USACE Phase I report ADA063039): crest 375.0, principal spillway box weir 359.5,
emergency ogee 280 ft at 365.5 (report datum); lidar crest 374.6 so report elevations shifted -0.4 ft.
The principal spillway inlet shows in the lidar at ~360 ft, so the terrain carries it; check outflow against USGS 01480685.
