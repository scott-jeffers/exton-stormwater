"""Flow direction on the 10-ft DEM (streams burned 2 ft, as Exton) and the Upper East Branch + Marsh Creek watershed."""
import json, numpy as np, geopandas as gpd, rasterio, pyflwdir
from rasterio.features import rasterize, shapes as rshapes
from shapely.geometry import shape, Point
from shapely.ops import unary_union

ds = rasterio.open('dem10ft.tif'); a = ds.read(1).astype(np.float32)
st = gpd.read_file('gis/streams.gpkg').to_crs(2272)
burn = rasterize([(g, 1) for g in st.geometry], out_shape=a.shape, transform=ds.transform, all_touched=True)
a2 = a.copy(); a2[(burn == 1) & (a2 > -9000)] -= 2
fl = pyflwdir.from_dem(a2, nodata=-9999, transform=ds.transform, latlon=False, outlets='edge')
up = (fl.upstream_area('cell') * 100 / 27878400).astype(np.float32)  # sq mi
np.save('up10.npy', up); np.save('d8_10.npy', fl.to_array('d8'))

# USGS 01480700 East Branch Brandywine Creek near Downingtown (from the county gauge list)
g = [f for f in json.load(open('/home/claude/chesco/usgs_gauges.geojson'))['features'] if f['properties']['usgs_id'] == '01480700'][0]
gx, gy = gpd.GeoSeries([Point(g['geometry']['coordinates'])], crs=4326).to_crs(2272).iloc[0].coords[0]
r, c = ds.index(gx, gy); W = 15
w = up[r - W:r + W + 1, c - W:c + W + 1]; rr, cc = np.unravel_index(np.argmax(w), w.shape); r += rr - W; c += cc - W
print('gauge 01480700 snapped, DA sq mi', round(float(up[r, c]), 1), '(USGS publishes 60.6)')

# outlet: where the East Branch leaves HUC 020402050103 (its downstream HUC boundary)
H = json.load(open('/home/claude/chesco/huc12_bbox.geojson'))['features']
hu = gpd.GeoSeries([unary_union([shape(f['geometry']).buffer(0) for f in H if f['properties']['huc12'] in ('020402050101', '020402050103')])], crs=4326).to_crs(2272).iloc[0]
# walk downstream from the gauge until leaving the HUC (plus 300 ft)
idx = r * a.shape[1] + c
path = fl.path(idxs=np.array([idx]))[0][0]
out_i = path[-1]
for k, i in enumerate(path):
    x, y = ds.xy(*np.unravel_index(i, a.shape))
    if not hu.buffer(-50).contains(Point(x, y)):
        out_i = path[min(k + 30, len(path) - 1)]; break
orr, occ = np.unravel_index(out_i, a.shape); ox, oy = ds.xy(orr, occ)
print('outlet', round(ox), round(oy), 'DA sq mi', round(float(up[orr, occ]), 1), 'steps below gauge', k)
basin = fl.basins(xy=(np.array([ox]), np.array([oy])))
P = max([shape(gg) for gg, v in rshapes(basin.astype(np.uint8), transform=ds.transform) if v == 1], key=lambda z: z.area).buffer(0)
print('watershed sq mi', round(P.area / 27878400, 1), ' HUC pair sq mi', round(hu.area / 27878400, 1), ' overlap %', round(P.intersection(hu).area / hu.area * 100, 1))
gpd.GeoDataFrame({'name': ['Upper East Branch & Marsh Creek'], 'sqmi': [P.area / 27878400]}, geometry=[P], crs=2272).to_file('m03_watershed.gpkg')
gpd.GeoDataFrame({'name': ['M03 outlet', 'USGS 01480700'], 'da_sqmi': [float(up[orr, occ]), float(up[r, c])]},
                 geometry=[Point(ox, oy), Point(ds.xy(r, c))], crs=2272).to_file('m03_points.gpkg')
