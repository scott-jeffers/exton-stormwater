import numpy as np, geopandas as gpd, rasterio
from pysheds.grid import Grid
from shapely.geometry import Point, shape
s=gpd.read_file("vc_streams.gpkg")
vc=s[s.NAME=="Valley Creek"]
# endpoints
pts=[]
for g in vc.geometry:
    for ls in (g.geoms if g.geom_type.startswith("Multi") else [g]):
        pts+= [ls.coords[0], ls.coords[-1]]
ds=rasterio.open("dem10ft.tif"); a=ds.read(1)
el=[a[ds.index(x,y)] for x,y,*_ in pts]
i=int(np.argmin(el)); out=pts[i][:2]; print("outlet",out,el[i])
grid=Grid.from_raster("dem10ft.tif"); dem=grid.read_raster("dem10ft.tif")
# burn streams 10 ft to guide flow through culverts/bridges
from rasterio.features import rasterize
burn=rasterize([(g,1) for g in s.geometry],out_shape=a.shape,transform=ds.transform,all_touched=True)
dem2=dem.copy(); dem2[burn==1]-=10
pit=grid.fill_pits(dem2); fl=grid.fill_depressions(pit); inf=grid.resolve_flats(fl)
fdir=grid.flowdir(inf); acc=grid.accumulation(fdir)
r,c=ds.index(*out); w=acc[r-15:r+16,c-15:c+16]; rr,cc=np.unravel_index(np.argmax(w),w.shape); r+=rr-15;c+=cc-15
x,y=ds.xy(r,c); print("snapped",x,y,acc[r,c]*100/27878400,"sq mi")
cat=grid.catchment(x=x,y=y,fdir=fdir,xytype='coordinate')
cat=np.asarray(cat).astype(np.uint8)
shapes=[shape(g) for g,v in rasterio.features.shapes(cat,transform=ds.transform) if v==1]
ws=gpd.GeoDataFrame(geometry=[max(shapes,key=lambda p:p.area)],crs=2272)
ws['sqmi']=ws.area/27878400; print(ws.sqmi.values)
ws.to_file("watershed.gpkg")
np.save("acc10.npy",np.asarray(acc)); np.save("fdir10.npy",np.asarray(fdir))
gpd.GeoDataFrame(geometry=[Point(x,y)],crs=2272).to_file("outlet.gpkg")
