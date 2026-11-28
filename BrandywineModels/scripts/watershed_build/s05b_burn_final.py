"""Burn the cross-checked structure set (structures_final.gpkg) into the original 1 m DEM, then set reservoirs to normal pool.
Usage: s05b_burn_final.py <dem.tif> <workdir> <out.tif> [lake_name pool_ft]"""
import sys, numpy as np, geopandas as gpd, rasterio, shapely
from shapely.geometry import LineString
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
from scipy import ndimage

dem_file, WD, out_file = sys.argv[1:4]
ds = rasterio.open(dem_file); A = ds.read(1); H, W = A.shape; T = ds.transform
s = gpd.read_file(f'{WD}/structures_final.gpkg')
def notch(line, us, dsv, b):
    ext = line.buffer(b / 2 + 15)
    win = from_bounds(*ext.bounds, T).round_offsets().round_lengths()
    r0, c0, h, w = int(win.row_off), int(win.col_off), int(win.height), int(win.width)
    if r0 < 0 or c0 < 0 or r0 + h > H or c0 + w > W: return 0
    sub = A[r0:r0 + h, c0:c0 + w]; rr, cc = np.indices(sub.shape)
    P = shapely.points(T.c + (c0 + cc.ravel() + 0.5) * T.a, T.f + (r0 + rr.ravel() + 0.5) * T.e)
    dd = shapely.distance(P, line).reshape(sub.shape); tt = (shapely.line_locate_point(line, P) / line.length).reshape(sub.shape)
    prof = us + (dsv - us) * tt; newz = np.where(dd <= b / 2, prof, prof + (dd - b / 2))
    m = (dd <= b / 2 + 15) & (sub > -9000); sub[m] = np.minimum(sub[m], newz[m]).astype(np.float32); A[r0:r0 + h, c0:c0 + w] = sub
    return 1
def ext10(g):
    co = list(g.coords); p0 = np.array(co[0][:2]); p1 = np.array(co[-1][:2])
    u0 = p0 - np.array(co[1][:2]); u0 /= np.linalg.norm(u0) + 1e-9; u1 = p1 - np.array(co[-2][:2]); u1 /= np.linalg.norm(u1) + 1e-9
    return LineString([tuple(p0 + u0 * 10)] + [q[:2] for q in co] + [tuple(p1 + u1 * 10)])
n = 0
for _, r in s.iterrows():
    g = r.geometry if r.geometry.geom_type == 'LineString' else max(r.geometry.geoms, key=lambda x: x.length)
    n += notch(ext10(g) if r.kind == 'Culvert' else g, r.us_inv, r.ds_inv, max(3.0, r.width_ft))
print('burned/notched', n, 'of', len(s))
if len(sys.argv) > 5:
    lake, pool = sys.argv[4], float(sys.argv[5])
    wt = gpd.read_file('/home/claude/ebb/gis/water.gpkg').to_crs(2272); L = wt[wt.NAME == lake].geometry.iloc[0]
    win = from_bounds(*L.buffer(300).bounds, T).round_offsets().round_lengths(); r0, c0 = int(win.row_off), int(win.col_off)
    sub = A[r0:r0 + int(win.height), c0:c0 + int(win.width)]; Tw = ds.window_transform(win)
    inpoly = ~geometry_mask([L], out_shape=sub.shape, transform=Tw)
    lab, _ = ndimage.label((sub > -9000) & (sub <= np.median(sub[inpoly & (sub > -9000)]) + 0.2), structure=np.ones((3, 3)))
    ids = np.unique(lab[inpoly]); ids = ids[ids > 0]
    big = max(ids, key=lambda i: (lab == i).sum())
    m = (inpoly | (lab == big)) & (sub > -9000) & (sub < pool)
    sub[m] = pool; A[r0:r0 + int(win.height), c0:c0 + int(win.width)] = sub
    print(lake, 'set to', pool, 'ft over', round(m.sum() * 3.2808 ** 2 / 43560, 1), 'ac')
prof = ds.profile; prof.update(BIGTIFF='YES')
with rasterio.open(out_file, 'w', **prof) as o: o.write(A, 1)
