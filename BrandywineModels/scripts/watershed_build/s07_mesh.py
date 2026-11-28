"""2D perimeter, outlet BC line and mesh points (Exton recipe, no culvert connections since culverts are burned in).
Usage: s07_mesh.py <watershed.gpkg> <outlet points gpkg> <outdir> <base ft> <fine ft>"""
import sys, math, numpy as np, geopandas as gpd, rasterio, shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import split, linemerge
from scipy.spatial import cKDTree

ws_file, pts_file, OUT, base, fine = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
ws = gpd.read_file(ws_file).geometry.iloc[0]
out = gpd.read_file(pts_file).geometry.iloc[0]
d10 = rasterio.open('/home/claude/ebb/dem10ft.tif'); up = np.load('/home/claude/ebb/up10.npy')
d8 = np.load('/home/claude/ebb/d8_10.npy')
import pyflwdir
fl = pyflwdir.from_array(d8, ftype='d8', transform=d10.transform, latlon=False)
# flow direction at the outlet: walk 40 cells upstream along the max-DA path to get the channel direction
r, c = d10.index(out.x, out.y)
path_up = [(r, c)]
for _ in range(40):
    rr, cc = path_up[-1]; best = None
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == dc == 0: continue
            r2, c2 = rr + dr, cc + dc
            if up[r2, c2] < up[rr, cc] and (best is None or up[r2, c2] > up[best]): best = (r2, c2)
    path_up.append(best)
(xa, ya), (xb, yb) = d10.xy(*path_up[-1]), d10.xy(*path_up[8])
vx, vy = xb - xa, yb - ya; L = math.hypot(vx, vy); vx, vy = vx / L, vy / L
cx, cy = d10.xy(*path_up[3]); nx, ny = -vy, vx
cut = LineString([(cx - nx * 3000, cy - ny * 3000), (cx + nx * 3000, cy + ny * 3000)])
poly = ws.buffer(30, join_style=2).buffer(-120).buffer(110).simplify(20)
keep = max(split(poly, cut).geoms, key=lambda p: p.area)
keep = Polygon(keep.exterior).simplify(20)
bc = keep.exterior.intersection(cut.buffer(0.5))
bcl = [g for g in getattr(bc, 'geoms', [bc]) if g.length > 5]
bcline = max(bcl, key=lambda g: g.length)
bcline = LineString(list(bcline.coords)) if bcline.geom_type == 'LineString' else linemerge(bcline)
# channel slope near outlet for the normal-depth BC (from 10-ft DEM along the path)
z = d10.read(1)
zs = [z[p] for p in path_up[:40]]; slope = max((zs[-1] - zs[0]) / (40 * 10 * 1.2), 0.0005)
print('perimeter sq mi', round(keep.area / 27878400, 2), 'BC line ft', round(bcline.length), 'outlet slope', round(slope, 5))
gpd.GeoDataFrame({'name': ['Perimeter']}, geometry=[keep], crs=2272).to_file(f'{OUT}/perimeter.gpkg')
gpd.GeoDataFrame({'name': ['Outlet'], 'slope': [slope]}, geometry=[bcline], crs=2272).to_file(f'{OUT}/bcline.gpkg')

# ---- points: base grid + fine grid along streams draining >= 300 ac (Exton rule)
inner = keep.buffer(-0.6 * base)
x0, y0, x1, y1 = keep.bounds
def grid(s, poly):
    xs = np.arange(np.floor(x0 / s) * s + s / 2, x1, s); ys = np.arange(np.floor(y0 / s) * s + s / 2, y1, s)
    X, Y = np.meshgrid(xs, ys); p = np.c_[X.ravel(), Y.ravel()]
    return p[shapely.contains_xy(poly, p[:, 0], p[:, 1])]
pts = grid(base, inner)
st = gpd.read_file('/home/claude/ebb/gis/streams.gpkg').to_crs(2272)
st = st[st.intersects(keep)].explode(index_parts=False)
big = []
for g in st.geometry:
    if g.length < 50: continue
    m = g.interpolate(0.5, normalized=True); r, c = d10.index(m.x, m.y)
    if float(up[max(r - 3, 0):r + 4, max(c - 3, 0):c + 4].max()) * 640 >= 300: big.append(g)
zone = shapely.union_all([g.buffer(2 * fine) for g in big]).intersection(inner)
print('refine zone ac', round(zone.area / 43560))
pts = pts[~shapely.contains_xy(zone.buffer(base * 0.3), pts[:, 0], pts[:, 1])]
pts = np.vstack([pts, grid(fine, zone)])
tree = cKDTree(pts); drop = {j for i, j in tree.query_pairs(r=fine * 0.35)}
pts = np.delete(pts, list(drop), axis=0)
pts = pts[shapely.contains_xy(keep.buffer(-0.5 * fine), pts[:, 0], pts[:, 1])]
print('mesh points', len(pts))
np.save(f'{OUT}/mesh_points.npy', pts)
