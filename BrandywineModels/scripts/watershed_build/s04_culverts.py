"""Exton culvert/bridge recipe for a new model area.
Finds road embankments that block streams in the 1 m DEM, sizes a culvert for each (10-yr Atlas 14 rational Q),
notches bridges (DA >= 1 sq mi) and burns culverts into the terrain.
Usage: python3 s04_culverts.py <watershed.gpkg> <dem_1m.tif> <outdir>
"""
import sys, math, numpy as np, pandas as pd, geopandas as gpd, rasterio, pyflwdir, shapely
from scipy.ndimage import minimum_filter
from shapely.geometry import Point, LineString
from rasterio.windows import from_bounds

ws_file, dem_file, OUT = sys.argv[1:4]
ws = gpd.read_file(ws_file).geometry.iloc[0]
ds = rasterio.open(dem_file); A = ds.read(1); H, W = A.shape; T = ds.transform
A[A == -9999] = np.nan
d10 = rasterio.open('/home/claude/ebb/dem10ft.tif'); a10 = d10.read(1).astype(np.float32)
up = np.load('/home/claude/ebb/up10.npy'); d8 = np.load('/home/claude/ebb/d8_10.npy')

# ---- DEM flow paths (10 ft grid, >= 10 ac) to catch unmapped ditches/swales
fl10 = pyflwdir.from_array(d8, ftype='d8', transform=d10.transform, latlon=False)
feats = fl10.streams(mask=up * 640 >= 10, min_sto=1)
fl = gpd.GeoDataFrame.from_features(feats, crs=2272)
fl = fl[fl.intersects(ws)]
st = gpd.read_file('/home/claude/ebb/gis/streams.gpkg').to_crs(2272)
st = st[st.intersects(ws)].explode(index_parts=False)
st = st[st.length > 5][['NAME', 'HIDDEN', 'geometry']]; st['src'] = 'county_stream'
stu = st.buffer(40).union_all()
near = fl.geometry.apply(lambda g: g.buffer(1).intersection(stu).area / max(g.buffer(1).area, 1))
fl = fl[near < 0.5].copy(); fl['NAME'] = 'DEM flow path'; fl['HIDDEN'] = ''; fl['src'] = 'dem_flowpath'
lines = pd.concat([st, fl[['NAME', 'HIDDEN', 'src', 'geometry']]], ignore_index=True).explode(index_parts=False)
print('lines', lines.src.value_counts().to_dict())

roads = gpd.read_file('/home/claude/ebb/gis/roads.gpkg').to_crs(2272); rsi = roads.sindex
rname_col = 'RD_NAME_FULL' if 'RD_NAME_FULL' in roads.columns else roads.columns[0]

# ---- candidates (embankments across flow lines)
Amin = minimum_filter(np.nan_to_num(A, nan=1e4), size=5)
step = 1.5
def zs(pts):
    out = []
    for p in pts:
        r, c = ds.index(p.x, p.y)
        out.append(Amin[r, c] if 0 <= r < H and 0 <= c < W and Amin[r, c] < 1e4 else np.nan)
    return np.array(out)
recs = []
for name, hid, src, g in lines[['NAME', 'HIDDEN', 'src', 'geometry']].itertuples(index=False):
    if g.geom_type != 'LineString': continue
    n = int(g.length / step) + 1
    if n < 8: continue
    d = np.linspace(0, g.length, n); pts = [g.interpolate(t) for t in d]
    z = zs(pts)
    if np.isnan(z).mean() > 0.2: continue
    z = pd.Series(z).interpolate(limit_direction='both').values
    zc = np.minimum.accumulate(z); blocked = (z - zc) > 1.0
    i = 0
    while i < n:
        if not blocked[i]: i += 1; continue
        s = i
        while i < n and blocked[i]: i += 1
        e = min(i, n - 1); s0 = max(s - 1, 0)
        crest = z[s:e + 1].max(); k = max(1, int(30 / step))
        relief = crest - max(np.median(z[max(0, s0 - k):s0 + 1]), np.median(z[e:min(n, e + k)]))
        L = d[e] - d[s0]
        if relief >= 3.0 and L >= 12:
            p_up, p_dn = pts[s0], pts[e]; pc = pts[s + int(np.argmax(z[s:e + 1]))]
            rr, cc = d10.index(p_up.x, p_up.y); da = float(up[max(rr - 3, 0):rr + 4, max(cc - 3, 0):cc + 4].max()) * 640
            seg = LineString([(q.x, q.y) for q in pts[s0:e + 1]])
            hit = list(rsi.query(seg.buffer(25)))
            recs.append(dict(src=src, stream=name, us_inv=float(zc[s0]), ds_inv=float(min(z[e], zc[s0])), crest=float(crest), relief=float(relief),
                             length=float(L), da_ac=da, road=(roads.iloc[hit[0]][rname_col] if hit else None),
                             us_x=p_up.x, us_y=p_up.y, cx=pc.x, cy=pc.y, geometry=seg))
g = gpd.GeoDataFrame(recs, crs=2272)
print('raw candidates', len(g))

# ---- filter: real ponding upstream, DA >= 5 ac, not in quarries
fill = pyflwdir.dem.fill_depressions(a10, nodata=-9999, outlets='edge')[0]; fd = fill - a10
def fdmax(x, y, r=3):
    rr, cc = d10.index(x, y); return float(fd[max(rr - r, 0):rr + r + 1, max(cc - r, 0):cc + r + 1].max())
g['pond_us'] = [fdmax(x, y) for x, y in zip(g.us_x, g.us_y)]
lu = gpd.read_file('/home/claude/ebb/gis/lulc.gpkg').to_crs(2272)
mine = lu[lu.LU_TYPE == '11000'].buffer(50).union_all() if (lu.LU_TYPE == '11000').any() else None
g['in_quarry'] = g.geometry.intersects(mine) if mine is not None else False
k = g[(~g.in_quarry) & (g.da_ac >= 5) & (g.pond_us >= 1.0)].sort_values('da_ac', ascending=False)
sel = []
for i, r in k.iterrows():
    p = r.geometry.centroid
    if all(p.distance(k.loc[j].geometry.centroid) > 60 for j in sel): sel.append(i)
k = k.loc[sel].reset_index(drop=True)
print('after filter/dedupe', len(k))

# ---- size (Atlas 14 10-yr rational, same as Exton)
dur = np.array([5, 10, 15, 30, 60, 120, 180]); dep = np.array([0.537, 0.858, 1.08, 1.57, 2.05, 2.48, 2.70])
def i10(tc): return np.interp(np.log(tc), np.log(dur), np.log(dep / (dur / 60)))
def Q10(da):
    qr = lambda a: 0.39 * math.exp(i10(10 + 25 * math.sqrt(a / 640))) * a
    return qr(da) if da <= 200 else qr(200) * (da / 200) ** 0.6
pipes = [1.25, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6]
cap = lambda D: 2.36 * D ** 2.5
rows = []
for i, r in k.iterrows():
    q = Q10(r.da_ac); us = r.us_inv; ds_ = r.ds_inv
    if ds_ >= us - 0.05: ds_ = us - max(0.005 * r.length, 0.1)
    maxrise = max(1.25, min(r.crest - us - 1.0, 12)); shape = 1; rise = None; span = 0; nb = 1
    for D in pipes:
        if D <= maxrise and cap(D) >= q: rise = D; break
    if rise is None:
        D = max([p for p in pipes if p <= maxrise] or [1.25]); nb = math.ceil(q / cap(D))
        if nb <= 3 and r.da_ac <= 500: rise = D
        else:
            shape = 2; rise = max(min(math.floor(maxrise), 10), 2)
            B = q / (3.3 * rise ** 1.5); nb = max(1, math.ceil(B / 16)); span = min(max(3, math.ceil(B / nb)), 16)
    rows.append(dict(cid=f'C{i + 1:04d}', shape=shape, rise=rise, span=span, barrels=nb, length=max(r.length, 20), us_inv=round(us, 2),
                     ds_inv=round(ds_, 2), crest=round(r.crest, 2), relief=round(r.relief, 1), q10_est=round(q, 1), da_ac=round(r.da_ac, 1),
                     src=r.src, stream=r.stream, road=r.road, geometry=r.geometry))
c = gpd.GeoDataFrame(rows, crs=2272)
isbr = (c.da_ac >= 640) & (c.relief < 10) & (c.length < 150)
br, cu = c[isbr].copy(), c[~isbr].copy()
br['bottom_w'] = [max(10, 12 * math.sqrt(d / 640)) for d in br.da_ac]
print('bridges', len(br), 'culverts', len(cu))

br.to_file(f'{OUT}/bridge_openings.gpkg'); cu.to_file(f'{OUT}/culverts.gpkg')
c.drop(columns='geometry').to_csv(f'{OUT}/Culvert_Table.csv', index=False)
fl.to_file(f'{OUT}/dem_flowpaths.gpkg')
