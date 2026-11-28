"""1 m (3.28 ft) DEM in EPSG:2272 feet for one model area, clipped to watershed + buffer."""
import glob, sys, numpy as np, rasterio, geopandas as gpd
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin
from rasterio.features import geometry_mask

ws_file, out_file, buf = sys.argv[1], sys.argv[2], float(sys.argv[3])
ws = gpd.read_file(ws_file).geometry.iloc[0].buffer(buf)
cs = 3.280833333
l, b, r, t = ws.bounds
l = np.floor(l / 10) * 10; t = np.ceil(t / 10) * 10
W = int(np.ceil((r - l) / cs)); H = int(np.ceil((t - b) / cs))
tr = from_origin(l, t, cs, cs)
print('grid', W, H, round(W * H / 1e6), 'M cells')
out = np.full((H, W), np.nan, np.float32)
for f in sorted(glob.glob('/home/claude/ebb/lidar/*.tif')):
    with rasterio.open(f) as s:
        tmp = np.full((H, W), np.nan, np.float32)
        reproject(rasterio.band(s, 1), tmp, src_nodata=s.nodata, dst_nodata=np.nan, dst_transform=tr, dst_crs='EPSG:2272',
                  resampling=Resampling.bilinear)
    m = np.isnan(out) & ~np.isnan(tmp); out[m] = tmp[m] * 3.28083333
    del tmp
mask = geometry_mask([ws], out_shape=(H, W), transform=tr)
out[mask] = np.nan
print('nodata inside area', int((np.isnan(out) & ~mask).sum()))
prof = dict(driver='GTiff', width=W, height=H, count=1, dtype='float32', crs='EPSG:2272', transform=tr, nodata=-9999,
            tiled=True, blockxsize=512, blockysize=512, compress='deflate', predictor=3, BIGTIFF='IF_SAFER')
with rasterio.open(out_file, 'w', **prof) as o:
    o.write(np.where(np.isnan(out), -9999, out).astype(np.float32), 1)
