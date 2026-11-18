import numpy as np, geopandas as gpd, rasterio, pyflwdir
from rasterio.features import rasterize, shapes as rshapes
from shapely.geometry import shape, Point
ds=rasterio.open("dem10_enf.tif"); a=ds.read(1).astype(np.float32)
s=gpd.read_file("vc_streams.gpkg")
allst=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Rivers_and_Streams",bbox=tuple(ds.bounds))
burn=rasterize([(g,1) for g in allst.geometry],out_shape=a.shape,transform=ds.transform,all_touched=True)
a2=a.copy(); a2[burn==1]-=2   # stream burning to carry flow through road fills/culverts
fl=pyflwdir.from_dem(a2,nodata=-9999,transform=ds.transform,latlon=False,outlets="edge")
uparea=fl.upstream_area("cell")  # cells
up=uparea*100/27878400
np.save("up10.npy",up.astype(np.float32)); np.save("d8_10.npy",fl.to_array("d8"))
# outlet: on Valley Creek just above confluence with EB Brandywine
vc=s[s.NAME=="Valley Creek"]
best=None
for g in vc.geometry.explode(index_parts=False):
    for p in (g.coords[0],g.coords[-1]):
        e=a[ds.index(p[0],p[1])]
        if best is None or e<best[0]: best=(e,g,p)
e,g,p=best
q=g.interpolate(300) if Point(g.coords[0]).distance(Point(p))<1 else g.interpolate(g.length-300)
r,c=ds.index(q.x,q.y); W=4; w=up[r-W:r+W+1,c-W:c+W+1]; rr,cc=np.unravel_index(np.argmax(w),w.shape); r+=rr-W;c+=cc-W
print("outlet",ds.xy(r,c),"DA sq mi",up[r,c])
basin=fl.basins(xy=(np.array([ds.xy(r,c)[0]]),np.array([ds.xy(r,c)[1]])))
P=max([shape(gg) for gg,v in rshapes(basin.astype(np.uint8),transform=ds.transform) if v==1],key=lambda z:z.area)
ws=gpd.GeoDataFrame({'sqmi':[P.area/27878400]},geometry=[P.buffer(0)],crs=2272); print(ws.sqmi.values,P.bounds)
print("edge", basin[0].any(),basin[-1].any(),basin[:,0].any(),basin[:,-1].any())
ws.to_file("watershed.gpkg"); gpd.GeoDataFrame(geometry=[Point(ds.xy(r,c))],crs=2272).to_file("outlet.gpkg")
inside=s.within(P.buffer(100)); print("VC streams inside mi",s[inside].length.sum()/5280,"outside",s[~inside].length.sum()/5280)
