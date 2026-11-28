"""10-ft DEM (EPSG:2272, ft) over the whole study area, for delineation and mesh planning."""
import glob, numpy as np, rasterio, geopandas as gpd
from rasterio.warp import reproject, Resampling
from rasterio.transform import from_origin

sa = gpd.read_file('gis/study_area.gpkg').geometry.iloc[0]
l, b, r, t = sa.bounds; cs = 10.0
l = np.floor(l / cs) * cs; t = np.ceil(t / cs) * cs
W = int(np.ceil((r - l) / cs)); H = int(np.ceil((t - b) / cs))
tr = from_origin(l, t, cs, cs)
out = np.full((H, W), np.nan, np.float32)
for f in sorted(glob.glob('lidar/*.tif')):
    with rasterio.open(f) as s:
        tmp = np.full((H, W), np.nan, np.float32)
        reproject(rasterio.band(s, 1), tmp, src_nodata=s.nodata, dst_nodata=np.nan, dst_transform=tr, dst_crs='EPSG:2272',
                  resampling=Resampling.average)
    tmp *= 3.28083333  # m -> US survey ft
    m = np.isnan(out) & ~np.isnan(tmp); out[m] = tmp[m]
    print(f.split('/')[-1], 'filled', int(m.sum()))
print('nodata cells', int(np.isnan(out).sum()), 'of', out.size)
prof = dict(driver='GTiff', width=W, height=H, count=1, dtype='float32', crs='EPSG:2272', transform=tr, nodata=-9999,
            tiled=True, blockxsize=512, blockysize=512, compress='deflate', predictor=3)
with rasterio.open('dem10ft.tif', 'w', **prof) as o:
    o.write(np.where(np.isnan(out), -9999, out), 1)
