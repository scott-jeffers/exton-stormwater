import numpy as np, geopandas as gpd, rasterio
from rasterio.features import shapes as rshapes
from shapely.geometry import Point, shape
from shapely.ops import linemerge, substring
ds=rasterio.open("dem10ft.tif"); a=ds.read(1)
acc=np.load("acc10.npy"); fdir=np.load("fdir10.npy")
s=gpd.read_file("vc_streams.gpkg"); vc=s[s.NAME=="Valley Creek"]
# point 400 ft upstream from the lowest end along the lowest segment
best=None
for g in vc.geometry:
    for ls in (g.geoms if g.geom_type.startswith("Multi") else [g]):
        for end,frac in ((0,400),(1,-400)):
            p=ls.coords[0] if end==0 else ls.coords[-1]
            e=a[ds.index(p[0],p[1])]
            if best is None or e<best[0]: best=(e,ls,end)
e,ls,end=best
d=min(400,ls.length/2); p=ls.interpolate(d if end==0 else ls.length-d)
r,c=ds.index(p.x,p.y); W=5
w=acc[r-W:r+W+1,c-W:c+W+1]; rr,cc=np.unravel_index(np.argmax(w),w.shape); r+=rr-W;c+=cc-W
print("outlet acc sqmi",acc[r,c]*100/27878400)
# own catchment tracing using D8 esri codes
dirs={64:(-1,0),128:(-1,1),1:(0,1),2:(1,1),4:(1,0),8:(1,-1),16:(0,-1),32:(-1,-1)}
H,Wd=fdir.shape
cat=np.zeros((H,Wd),bool); cat[r,c]=True; stack=[(r,c)]
while stack:
    i,j=stack.pop()
    for code,(di,dj) in dirs.items():
        ni,nj=i-di,j-dj  # neighbor that would flow into (i,j) has direction (di,dj)
        if 0<=ni<H and 0<=nj<Wd and not cat[ni,nj] and fdir[ni,nj]==code:
            cat[ni,nj]=True; stack.append((ni,nj))
print("cells",cat.sum(), cat.sum()*100/27878400)
polys=[shape(g) for g,v in rshapes(cat.astype(np.uint8),transform=ds.transform) if v==1]
P=max(polys,key=lambda q:q.area)
ws=gpd.GeoDataFrame({'sqmi':[P.area/27878400]},geometry=[P],crs=2272); print(ws.sqmi.values, P.bounds)
# does it touch the bbox edge?
print("edge touch:", cat[0,:].any(),cat[-1,:].any(),cat[:,0].any(),cat[:,-1].any())
ws.to_file("watershed.gpkg"); gpd.GeoDataFrame(geometry=[Point(ds.xy(r,c))],crs=2272).to_file("outlet.gpkg")
