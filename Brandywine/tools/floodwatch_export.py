"""Build one Brandywine Flood Watch scenario from the per-model results.
usage: python3 floodwatch_export.py <scenario id> <plan tag e.g. p17> "<name>" [models comma]
Reads out/{M}_{plan}_depth_ft.tif (20-ft depth), cells/{M}_{plan}.npz (cell max WSE), out/{M}_{plan}_bldg.geojson.
Writes /home/claude/exton-stormwater/Brandywine/data/scenarios/<id>.js in the Valley Creek dashboard format."""
import sys, os, io, json, base64, numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.warp import reproject, calculate_default_transform, transform_bounds
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.features import shapes as rshapes
from scipy.spatial import cKDTree
from shapely.geometry import LineString, mapping, shape as sshape, box
from PIL import Image
sid, plan, name = sys.argv[1:4]
MODELS = sys.argv[4].split(',') if len(sys.argv) > 4 else ['M03', 'M12', 'M02', 'M04', 'M05']
OUT = '/home/claude/exton-stormwater/Brandywine/data/scenarios'; os.makedirs(OUT, exist_ok=True)
STRUCT = {'M03': 'ebb/m03', 'M02': 'ebb/m02v2' if os.path.exists('/home/claude/ebb/m02v2/structures_final.gpkg') else 'ebb/m02',
          'M12': 'wb/m12', 'M04': 'wb/m04', 'M05': 'bm/m05'}
CRS = 'EPSG:2272'; R = 30.0
have = [m for m in MODELS if os.path.exists(f'out/{m}_{plan}_depth_ft.tif')]
have0 = list(have)
if not have: sys.exit('no models for ' + plan)
# ---- merged depth grid (max of models) at 30 ft
bb = [1e12, 1e12, -1e12, -1e12]
for m in have:
    with rasterio.open(f'out/{m}_{plan}_depth_ft.tif') as r:
        b = r.bounds; bb = [min(bb[0], b.left), min(bb[1], b.bottom), max(bb[2], b.right), max(bb[3], b.top)]
if plan in ('p03', 'p14', 'p17'):   # make room for the Valley Creek model
    from pyproj import Transformer
    tv = Transformer.from_crs(4326, 2272, always_xy=True); a_ = tv.transform(-75.684, 39.967); b_ = tv.transform(-75.578, 40.057)
    bb = [min(bb[0], a_[0]), min(bb[1], a_[1]), max(bb[2], b_[0]), max(bb[3], b_[1])]
W = int((bb[2] - bb[0]) / R) + 1; H = int((bb[3] - bb[1]) / R) + 1; tr = from_origin(bb[0], bb[3], R, R)
D = np.full((H, W), np.nan, 'float32')
for m in have:
    with rasterio.open(f'out/{m}_{plan}_depth_ft.tif') as r:
        t = np.full((H, W), np.nan, 'float32')
        reproject(rasterio.band(r, 1), t, dst_transform=tr, dst_crs=CRS, resampling=Resampling.max, src_nodata=np.nan, dst_nodata=np.nan)
    D = np.fmax(D, t)
# ---- Valley Creek (Exton/West Whiteland) model from the West Whiteland dashboard, same design storms
VC = {'p03': '10yr-6-hr', 'p14': '10yr-24-hr', 'p17': '100yr-24-hr'}.get(plan)
vcs = None
if VC and os.path.exists(f'/home/claude/exton-stormwater/Dashboard/data/scenarios/{VC}.js'):
    t = open(f'/home/claude/exton-stormwater/Dashboard/data/scenarios/{VC}.js').read(); vcs = json.loads(t[t.index('=', t.index(']')) + 1:].rstrip().rstrip(';'))
    v = np.array(Image.open(io.BytesIO(base64.b64decode(vcs['value_png'].split(',')[1]))).convert('L')).astype('float32')
    v = np.where(v == 255, np.nan, v * vcs['value_scale'])
    (s_, w_), (n_, e_) = vcs['bounds']; from pyproj import Transformer
    tm = Transformer.from_crs(4326, 3857, always_xy=True); x0, y0 = tm.transform(w_, s_); x1, y1 = tm.transform(e_, n_)
    vtr = rasterio.transform.from_bounds(x0, y0, x1, y1, v.shape[1], v.shape[0])
    t2 = np.full((H, W), np.nan, 'float32')
    reproject(v, t2, src_transform=vtr, src_crs='EPSG:3857', dst_transform=tr, dst_crs=CRS, resampling=Resampling.average, src_nodata=np.nan, dst_nodata=np.nan)
    t2[t2 < 0.5] = np.nan
    from scipy import ndimage
    lab, nl = ndimage.label(np.isfinite(t2)); sz = ndimage.sum(np.ones_like(lab), lab, range(1, nl + 1)); sm = np.zeros(nl + 1, bool); sm[1:] = sz < 18; t2[sm[lab]] = np.nan
    D = np.fmax(D, t2); have = have + ['M01']
# ---- display images (web mercator, ~60 ft)
dt, dw, dh = calculate_default_transform(CRS, 'EPSG:3857', W, H, *bb, resolution=18.3)
d3 = np.full((dh, dw), np.nan, 'float32')
reproject(D, d3, src_transform=tr, src_crs=CRS, dst_transform=dt, dst_crs='EPSG:3857', resampling=Resampling.max, src_nodata=np.nan, dst_nodata=np.nan)
west, south, east, north = transform_bounds('EPSG:3857', 'EPSG:4326', *rasterio.transform.array_bounds(dh, dw, dt))
bins = [0.25, 0.5, 1, 2, 3, 5, 1e9]
cols = [(173, 216, 240, 150), (116, 180, 230, 175), (49, 130, 206, 195), (20, 90, 180, 210), (8, 48, 140, 225), (60, 10, 110, 235)]
rgba = np.zeros((dh, dw, 4), 'uint8')
for i, c in enumerate(cols): rgba[(d3 >= bins[i]) & (d3 < bins[i + 1])] = c
def uri(img):
    bio = io.BytesIO(); img.save(bio, 'PNG', optimize=True); return 'data:image/png;base64,' + base64.b64encode(bio.getvalue()).decode()
vis = uri(Image.fromarray(rgba, 'RGBA').quantize(colors=8, method=Image.Quantize.FASTOCTREE) if False else Image.fromarray(rgba, 'RGBA'))
val = np.where(np.isfinite(d3), np.clip(np.round(d3 * 10), 0, 249), 255).astype('uint8'); vimg = uri(Image.fromarray(val, 'L'))
def dep(x, y):
    c = ((np.asarray(x) - bb[0]) / R).astype(int); r = ((bb[3] - np.asarray(y)) / R).astype(int)
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W); out = np.full(len(c), np.nan); out[ok] = D[r[ok], c[ok]]; return out
to4326 = lambda g: gpd.GeoSeries([g], crs=CRS).to_crs(4326).iloc[0]
rnd = lambda c: [round(c[0], 6), round(c[1], 6)]
area = box(*bb)
# ---- roads (screening: road points sampled on the 30-ft depth grid, stream channels excluded)
roads = gpd.read_file('/home/claude/bm/gis/roads.gpkg', bbox=tuple(bb)).to_crs(CRS)
streams = gpd.read_file('/home/claude/bm/gis/streams.gpkg', bbox=tuple(bb)).to_crs(CRS)
sb = streams.geometry.buffer(45).union_all()
DEMS = [rasterio.open(f'/home/claude/{g}/dem10ft.tif') for g in ('ebb', 'wb', 'bm')]
def ground(pts):
    z = np.full(len(pts), np.nan)
    for d in DEMS:
        v = np.array([q[0] for q in d.sample([(p.x, p.y) for p in pts])], float)
        nd = d.nodata if d.nodata is not None else -9999
        ok = np.isnan(z) & (v > -1000) & (v != nd); z[ok] = v[ok]
    return z
out_roads = []; dropped = 0
for _, r in roads.iterrows():
    g = r.geometry; g = max(getattr(g, 'geoms', [g]), key=lambda q: q.length); g = LineString([c[:2] for c in g.coords]); L = g.length
    if L < 1: continue
    n = max(2, int(L / 25) + 1); pts = [g.interpolate(t, normalized=True) for t in np.linspace(0, 1, n)]
    ds = dep([p.x for p in pts], [p.y for p in pts])
    if np.nanmax(np.nan_to_num(ds)) < 0.5: continue
    inch = np.array([sb.contains(p) for p in pts]); ds[inch] = np.nan
    wet = np.nan_to_num(ds) >= 0.5; i = 0
    while i < n:
        if wet[i]:
            j = i
            while j + 1 < n and wet[j + 1]: j += 1
            # bare-earth lidar has no bridge decks: drop runs that sit well below the road on both sides (a bridge span)
            ends = [g.interpolate(max(0, (i * L / (n - 1)) - 150)), g.interpolate(min(L, (j * L / (n - 1)) + 150))]
            zr = ground(pts[i:j + 1]); ze = ground(ends)
            if np.isfinite(ze).all() and np.nanmin(zr) < min(ze) - 8:
                dropped += 1; i = j + 1; continue
            seg = LineString([pts[max(i - 1, 0)], *pts[i:j + 1], pts[min(j + 1, n - 1)]]); gg = to4326(seg)
            fc = r.HWY_FUNCTIONAL_CLASS if isinstance(r.HWY_FUNCTIONAL_CLASS, str) else ''
            out_roads.append({'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': [rnd(c) for c in gg.coords]},
              'properties': {'name': (r.RD_NAME_FULL or r.RD_NAME or 'Unnamed road'), 'max_ft': round(float(np.nanmax(ds[i:j + 1])), 2),
               'len_ft': round((j - i + 1) * L / (n - 1)), 'evac': isinstance(r.EVAC_ROUTE_TYPE, str) and r.EVAC_ROUTE_TYPE.strip() not in ('', 'None'),
               'major': (r.RD_CLASS in ('Highway', 'Primary', 'Secondary')) or any(k in fc for k in ('Arterial', 'Expressway', 'Collector')),
               'fclass': fc, 'owner': r.RD_OWNER, 'cls': r.RD_CLASS}})
            i = j + 1
        else: i += 1
# ---- crossings: max WSE of low wet cells within 120 ft vs road crest
out_x = []
for m in have0:
    z = np.load(f'cells/{m}_{plan}.npz'); xy, wse, zm = z['xy'], z['wse'], z['zmin']; t = cKDTree(xy)
    s = gpd.read_file(f'/home/claude/{STRUCT[m]}/structures_final.gpkg').to_crs(CRS)
    for _, r in s.iterrows():
        if pd.isna(r.crest): continue
        c = r.geometry.centroid; ii = np.array(t.query_ball_point([c.x, c.y], 120))
        if not len(ii): continue
        ok = ii[(zm[ii] <= r.crest + 0.5) & ((wse[ii] - zm[ii]) > 0.3)]
        if not len(ok): continue
        w = float(wse[ok].max()); g = to4326(c)
        out_x.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': rnd(g.coords[0])},
          'properties': {'id': f'{m}-{r.cid}', 'kind': r.kind, 'road': r.road if isinstance(r.road, str) else '', 'stream': r.stream if isinstance(r.stream, str) else '',
           'wse': round(w, 2), 'crest': round(float(r.crest), 2), 'overtop_ft': round(w - float(r.crest), 2)}})
# ---- buildings (depth alongside the footprint, from bldg.py)
out_b = []
for m in have0:
    f = f'out/{m}_{plan}_bldg.geojson'
    if not os.path.exists(f): continue
    b = gpd.read_file(f); c = b.geometry.representative_point()
    for p, d, mu in zip(c, b.d, b.iloc[:, 1]):
        out_b.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(p.x, 6), round(p.y, 6)]}, 'properties': {'upi': str(mu), 'max_ft': round(float(d), 2)}})
if vcs:
    for f in vcs['roads']['features']:
        if f['properties']['max_ft'] >= 1.0: out_roads.append(f)
    for f in vcs['crossings']['features']: f['properties']['id'] = 'M01-' + str(f['properties']['id']); out_x.append(f)
    for f in vcs['buildings']['features']:
        if f['properties']['max_ft'] >= 1.5: out_b.append(f)
# ---- vector extent for SARTopo
cls = np.zeros(D.shape, 'uint8'); dd = np.nan_to_num(D, nan=0); cls[dd >= 1] = 1; cls[dd >= 3] = 2
ext = []
for geom, v in rshapes(cls, mask=cls > 0, transform=tr):
    g = sshape(geom)
    if g.area < 20000: continue
    g = g.simplify(25)
    if g.is_empty: continue
    m4 = mapping(to4326(g))
    def r6(c): return [round(c[0], 5), round(c[1], 5)] if isinstance(c[0], (int, float)) else [r6(x) for x in c]
    ext.append({'type': 'Feature', 'geometry': {'type': m4['type'], 'coordinates': r6(m4['coordinates'])}, 'properties': {'depth_class': '1-3 ft' if v == 1 else '3+ ft'}})
out_roads = [f for f in out_roads if f['properties']['max_ft'] >= 1.0]   # the dashboard's lowest road threshold
out_b = [f for f in out_b if f['properties']['max_ft'] >= 1.5]            # and lowest building threshold
stats = {'flooded_acres_0p5ft': round(float(np.nansum(D >= 0.5) * R * R / 43560), 1), 'max_depth_ft': round(float(np.nanmax(D)), 1),
         'roads_flooded': len(out_roads), 'road_names': sorted({x['properties']['name'] for x in out_roads}),
         'crossings_overtopped': sum(1 for x in out_x if x['properties']['overtop_ft'] > 0), 'buildings_wet': len(out_b), 'run_complete': True}
meta = {'id': sid, 'name': name, 'plan': plan, 'models': have}
obj = {'meta': meta, 'stats': stats, 'bounds': [[south, west], [north, east]], 'depth_png': vis, 'value_png': vimg, 'value_scale': 0.1,
       'roads': {'type': 'FeatureCollection', 'features': out_roads}, 'crossings': {'type': 'FeatureCollection', 'features': out_x},
       'buildings': {'type': 'FeatureCollection', 'features': out_b}, 'extent': {'type': 'FeatureCollection', 'features': ext}}
s = '(window.SCENARIO_DATA=window.SCENARIO_DATA||{})[' + json.dumps(sid) + ']=' + json.dumps(obj, separators=(',', ':')) + ';\n'
open(f'{OUT}/{sid}.js', 'w').write(s)
print(sid, have, 'bridge runs dropped', dropped, {k: v for k, v in stats.items() if k != 'road_names'}, round(len(s) / 1e6, 1), 'MB')
