"""Cross-check lidar-inferred culverts/bridges against PennDOT BMS2 structures and county road-crossing pipes.
- PennDOT match (<=150 ft): opening width from PennDOT (max span x spans), kind from PennDOT, keep inferred inverts.
- PennDOT with no match: if the lidar shows an embankment blocking the stream there (>=2 ft above both sides), add it
  as a notch along the stream through the structure; otherwise the bare-earth lidar is already open (deck removed) -> no change.
- County pipes crossing roads that look like culverts and are standalone (not tied into the storm network): if the lidar
  blocks along the pipe (>=2 ft), add a burned culvert along the pipe (size by Atlas 14 10-yr Q as before).
  Pipes connected to the storm network stay in the 1D pipe network instead (no double counting).
Writes <out>/structures_final.gpkg, <out>/crosscheck_log.csv and a summary.
Usage: s09_crosscheck.py <watershed.gpkg> <dem.tif> <workdir> <excluded cids>"""
import sys, math, numpy as np, pandas as pd, geopandas as gpd, rasterio
from shapely.geometry import LineString, Point
from shapely.ops import nearest_points

ws_file, dem_file, WD, excl = sys.argv[1], sys.argv[2], sys.argv[3], set(sys.argv[4].split(','))
ws = gpd.read_file(ws_file).geometry.iloc[0]
ds = rasterio.open(dem_file); A = ds.read(1); H, W = A.shape
def z(x, y):
    r, c = ds.index(x, y)
    return float(A[r, c]) if 0 <= r < H and 0 <= c < W and A[r, c] > -9000 else np.nan
d10 = rasterio.open('/home/claude/ebb/dem10ft.tif'); up = np.load('/home/claude/ebb/up10.npy')
def da_at(x, y, r=3):
    rr, cc = d10.index(x, y); return float(up[max(rr - r, 0):rr + r + 1, max(cc - r, 0):cc + r + 1].max()) * 640

cu = gpd.read_file(f'{WD}/culverts.gpkg').assign(kind_inf='Culvert'); br = gpd.read_file(f'{WD}/bridge_openings.gpkg').assign(kind_inf='Bridge')
inf = gpd.GeoDataFrame(pd.concat([cu, br], ignore_index=True), crs=2272); inf = inf[~inf.cid.isin(excl)].reset_index(drop=True)
inf['width_ft'] = [max(3.0, r.barrels * (r.span if r['shape'] == 2 else r.rise) + max(0, r.barrels - 1)) if r.kind_inf == 'Culvert' else r.bottom_w
                   for _, r in inf.iterrows()]
inf['source'] = 'Lidar-inferred'; inf['check'] = 'Lidar only'; inf['penndot_brkey'] = ''; inf['penndot_desc'] = ''; inf['pipe_id'] = ''

pdt = gpd.read_file('/home/claude/ebb/ref_gis/PennDOT_Structures_over_water.gpkg'); pdt = pdt[pdt.within(ws.buffer(-50))].reset_index(drop=True)
st = gpd.read_file('/home/claude/ebb/gis/streams.gpkg').to_crs(2272); st = st[st.intersects(ws)].explode(index_parts=False)
fp = gpd.read_file(f'{WD}/dem_flowpaths.gpkg')
lines = pd.concat([st[['geometry']], fp[['geometry']]], ignore_index=True)
lsi = lines.sindex
log = []

# ---- 1) PennDOT structures
nj = gpd.sjoin_nearest(pdt, inf[['cid', 'geometry']], max_distance=150, distance_col='dist', how='left')
nj = nj[~nj.index.duplicated()]
for i, r in nj.iterrows():
    open_w = float(np.nan_to_num(r.max_span_ft) * max(1, np.nan_to_num(r.spans)))
    open_w = open_w if open_w > 0 else float(np.nan_to_num(r.length_ft))
    desc = f"{r.kind}: {r.carries} over {r.crosses}; {int(np.nan_to_num(r.spans))} x {np.nan_to_num(r.max_span_ft):.0f} ft span; built {r.year_built}"
    if isinstance(r.cid, str):
        k = inf.index[inf.cid == r.cid][0]; old = inf.at[k, 'width_ft']
        if inf.at[k, 'penndot_brkey']:  # two PennDOT structures on one inferred crossing: keep the larger
            if open_w <= old: log.append(dict(id=r.brkey, action='PennDOT duplicate at same crossing (kept larger)', detail=desc)); continue
        inf.loc[k, ['width_ft', 'check', 'penndot_brkey', 'penndot_desc']] = [max(open_w, 3.0), 'Confirmed by PennDOT', r.brkey, desc]
        inf.at[k, 'kind_inf'] = r.kind
        log.append(dict(id=r.brkey, cid=r.cid, action='Matched: opening set from PennDOT', old_width_ft=round(old, 1), new_width_ft=round(open_w, 1), detail=desc))
        continue
    # unmatched: does lidar block the stream here?
    p = r.geometry
    cand = [lines.geometry.iloc[j] for j in lsi.query(p.buffer(80))]
    if not cand:
        log.append(dict(id=r.brkey, action='No stream line near structure; not added', detail=desc)); continue
    g = min(cand, key=lambda g: g.distance(p)); s = g.project(p); half = max(30, float(np.nan_to_num(r.length_ft)) / 2 + 30)
    pts = [g.interpolate(t) for t in np.linspace(max(0, s - half), min(g.length, s + half), 41)]
    zz = np.array([z(q.x, q.y) for q in pts])
    if np.isnan(zz).any():
        log.append(dict(id=r.brkey, action='Outside terrain; not added', detail=desc)); continue
    crest = zz[10:31].max(); ends = max(zz[:5].min(), zz[-5:].min())
    if crest - ends >= 2.0:
        us, dsv = zz[:5].min(), zz[-5:].min()
        if us < dsv: pts = pts[::-1]; us, dsv = dsv, us
        seg = LineString([(q.x, q.y) for q in pts])
        new = dict(cid=f'P{r.brkey}', kind_inf=r.kind, us_inv=round(us, 2), ds_inv=round(min(dsv, us - 0.1), 2), crest=round(crest, 2), relief=round(crest - ends, 1),
                   da_ac=round(da_at(p.x, p.y), 1), width_ft=max(open_w, 3.0), source='PennDOT', check='Added from PennDOT (lidar blocked)',
                   penndot_brkey=r.brkey, penndot_desc=desc, road=r.carries, stream=r.crosses, geometry=seg)
        inf = pd.concat([inf, gpd.GeoDataFrame([new], crs=2272)], ignore_index=True)
        log.append(dict(id=r.brkey, cid=new['cid'], action='Added: lidar blocked, opening from PennDOT', new_width_ft=round(open_w, 1), detail=desc))
    else:
        log.append(dict(id=r.brkey, action='Lidar already open (deck removed); no change', detail=desc))

# ---- 2) County pipes crossing roads
pp = gpd.read_file('/home/claude/ebb/ref_gis/County_Pipes_Crossing_Roads.gpkg'); pp = pp[pp.intersects(ws) & pp.likely_culvert].reset_index(drop=True)
allp = gpd.read_file('/home/claude/ebb/gis/sw_GravityMain.gpkg').to_crs(2272).explode(index_parts=False).reset_index(drop=True)
api = allp.sindex
pj = gpd.sjoin_nearest(pp, inf[['cid', 'geometry']], max_distance=80, distance_col='dist', how='left'); pj = pj[~pj.index.duplicated()]
dur = np.array([5, 10, 15, 30, 60, 120, 180]); dep = np.array([0.537, 0.858, 1.08, 1.57, 2.05, 2.48, 2.70])
i10 = lambda tc: np.interp(np.log(tc), np.log(dur), np.log(dep / (dur / 60)))
def Q10(da):
    qr = lambda a: 0.39 * math.exp(i10(10 + 25 * math.sqrt(a / 640))) * a
    return qr(da) if da <= 200 else qr(200) * (da / 200) ** 0.6
for i, r in pj.iterrows():
    g = r.geometry if r.geometry.geom_type == 'LineString' else max(r.geometry.geoms, key=lambda x: x.length)
    if isinstance(r.cid, str):
        k = inf.index[inf.cid == r.cid][0]
        if inf.at[k, 'check'] == 'Lidar only': inf.at[k, 'check'] = 'Confirmed by county pipe'
        inf.at[k, 'pipe_id'] = str(r.facility_id); log.append(dict(id=r.facility_id, cid=r.cid, action='Pipe matches inferred culvert', detail=f'{r.road}')); continue
    ends = [Point(g.coords[0]), Point(g.coords[-1])]
    touching = sum(1 for e in ends for j in api.query(e.buffer(3)) if not allp.geometry.iloc[j].equals(r.geometry) and allp.geometry.iloc[j].distance(e) < 3)
    if touching:
        log.append(dict(id=r.facility_id, action='Part of storm network; stays in 1D pipe network', detail=f'{r.road}')); continue
    co = list(g.coords); dx, dy = co[-1][0] - co[0][0], co[-1][1] - co[0][1]; L = math.hypot(dx, dy) or 1
    ext = LineString([(co[0][0] - dx / L * 10, co[0][1] - dy / L * 10)] + [c[:2] for c in co] + [(co[-1][0] + dx / L * 10, co[-1][1] + dy / L * 10)])
    zz = np.array([z(*ext.interpolate(t, normalized=True).coords[0]) for t in np.linspace(0, 1, 25)])
    if np.isnan(zz).any(): continue
    e1, e2 = zz[:3].min(), zz[-3:].min(); crest = zz[3:-3].max()
    if crest - max(e1, e2) < 2.0 or r.da_ac < 5:
        log.append(dict(id=r.facility_id, action='Lidar not blocked or tiny area; no change', detail=f'{r.road}; DA {r.da_ac:.0f} ac')); continue
    if e1 < e2: ext = LineString(list(ext.coords)[::-1]); e1, e2 = e2, e1
    q = Q10(r.da_ac); D = next((d for d in [1.25, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6] if 2.36 * d ** 2.5 >= q), 6)
    new = dict(cid=f'S{r.facility_id}', kind_inf='Culvert', us_inv=round(e1, 2), ds_inv=round(min(e2, e1 - 0.1), 2), crest=round(crest, 2), relief=round(crest - max(e1, e2), 1),
               da_ac=r.da_ac, width_ft=max(3.0, D), rise=D, source='County pipe', check='Added from county pipe (lidar blocked)', pipe_id=str(r.facility_id), road=r.road,
               stream='', geometry=ext)
    inf = pd.concat([inf, gpd.GeoDataFrame([new], crs=2272)], ignore_index=True)
    log.append(dict(id=r.facility_id, cid=new['cid'], action='Added: standalone pipe, lidar blocked', new_width_ft=D, detail=f'{r.road}; DA {r.da_ac:.0f} ac'))

inf['kind'] = inf.kind_inf
keep = ['cid', 'kind', 'source', 'check', 'road', 'stream', 'us_inv', 'ds_inv', 'crest', 'relief', 'da_ac', 'width_ft', 'penndot_brkey', 'penndot_desc', 'pipe_id', 'geometry']
out = gpd.GeoDataFrame(inf[keep], crs=2272); out.to_file(f'{WD}/structures_final.gpkg')
lg = pd.DataFrame(log); lg.to_csv(f'{WD}/crosscheck_log.csv', index=False)
print(lg.action.value_counts().to_string()); print(); print(out.groupby(['source', 'check']).size().to_string())
