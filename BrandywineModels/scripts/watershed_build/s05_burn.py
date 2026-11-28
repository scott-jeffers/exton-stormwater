"""Notch bridges and burn culverts into the 1 m DEM. Usage: s05_burn.py <dem.tif> <outdir> [exclude cids comma-separated]"""
import sys, math, numpy as np, geopandas as gpd, rasterio, shapely
from shapely.geometry import LineString
from rasterio.windows import from_bounds
dem_file, OUT = sys.argv[1:3]; excl = set(sys.argv[3].split(',')) if len(sys.argv) > 3 else set()
ds = rasterio.open(dem_file); A2 = ds.read(1); H, W = A2.shape; T = ds.transform
br = gpd.read_file(f'{OUT}/bridge_openings.gpkg'); cu = gpd.read_file(f'{OUT}/culverts.gpkg')
br = br[~br.cid.isin(excl)]; cu = cu[~cu.cid.isin(excl)]
def notch(line, us, dsv, b):
    ext = line.buffer(b / 2 + 15)
    win = from_bounds(*ext.bounds, T).round_offsets().round_lengths()
    r0, c0, h, w = int(win.row_off), int(win.col_off), int(win.height), int(win.width)
    if r0 < 0 or c0 < 0 or r0 + h > H or c0 + w > W: return False
    sub = A2[r0:r0 + h, c0:c0 + w]
    rows_, cols_ = np.indices(sub.shape)
    P = shapely.points(T.c + (c0 + cols_.ravel() + 0.5) * T.a, T.f + (r0 + rows_.ravel() + 0.5) * T.e)
    dd = shapely.distance(P, line).reshape(sub.shape); tt = (shapely.line_locate_point(line, P) / line.length).reshape(sub.shape)
    prof = us + (dsv - us) * tt; newz = np.where(dd <= b / 2, prof, prof + (dd - b / 2) * 1.0)
    m = (dd <= b / 2 + 15) & (sub > -9000); sub[m] = np.minimum(sub[m], newz[m]).astype(np.float32)
    A2[r0:r0 + h, c0:c0 + w] = sub; return True
nb_ = sum(notch(r.geometry, r.us_inv, r.ds_inv, r.bottom_w) for _, r in br.iterrows())
def ext10(seg):
    co = list(seg.coords); p0 = np.array(co[0][:2]); p1 = np.array(co[-1][:2])
    u0 = p0 - np.array(co[1][:2]); u0 /= np.linalg.norm(u0) + 1e-9; u1 = p1 - np.array(co[-2][:2]); u1 /= np.linalg.norm(u1) + 1e-9
    return LineString([tuple(p0 + u0 * 10)] + [q[:2] for q in co] + [tuple(p1 + u1 * 10)])
nc_ = sum(notch(ext10(r.geometry), r.us_inv, r.ds_inv, max(3.0, r.barrels * (r.span if r['shape'] == 2 else r.rise) + max(0, r.barrels - 1)))
          for _, r in cu.iterrows())
print('notched bridges', nb_, 'burned culverts', nc_)
prof = ds.profile; prof.update(BIGTIFF='YES')
with rasterio.open(f'{OUT}/' + dem_file.split('/')[-1].replace('.tif', '_hydro.tif'), 'w', **prof) as o: o.write(A2, 1)
print('excluded', sorted(excl))
