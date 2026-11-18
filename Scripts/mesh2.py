import numpy as np, geopandas as gpd, rasterio, json, math
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.ops import split, linemerge
from scipy.spatial import cKDTree
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
out=gpd.read_file("outlet.gpkg").geometry.iloc[0]
st=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Rivers_and_Streams",mask=ws.buffer(100)).explode(index_parts=False)
vc=st[st.NAME=="Valley Creek"]
# nearest VC segment to outlet, find direction
seg=min(vc.geometry,key=lambda g:g.distance(out))
d=seg.project(out); pA=seg.interpolate(max(d-400,0)); pB=seg.interpolate(max(d-200,0))
vx,vy=pB.x-pA.x,pB.y-pA.y; L=math.hypot(vx,vy); vx,vy=vx/L,vy/L
cx,cy=pB.x,pB.y; nx,ny=-vy,vx
cut=LineString([(cx-nx*3000,cy-ny*3000),(cx+nx*3000,cy+ny*3000)])
poly=ws.buffer(30,join_style=2).buffer(-120).buffer(110).simplify(20)
parts=split(poly,cut)
keep=max(parts.geoms,key=lambda p:p.area)
keep=Polygon(keep.exterior).simplify(20)
if keep.geom_type!='Polygon': keep=max(keep.geoms,key=lambda p:p.area)
bc=keep.exterior.intersection(cut.buffer(0.5))
bcl=[g for g in getattr(bc,'geoms',[bc]) if g.length>5]
bcline=max(bcl,key=lambda g:g.length) if bcl else None
print("perimeter pts",len(keep.exterior.coords),"area sqmi",keep.area/27878400,"bc len",bcline.length if bcline else None, bcline.geom_type)
keep=shapely.Polygon(shapely.segmentize(keep.exterior,60)) if False else keep
gpd.GeoDataFrame({'name':['ValleyCreek']},geometry=[keep],crs=2272).to_file("perimeter.gpkg")
bcline=LineString(list(bcline.coords)) if bcline.geom_type=="LineString" else linemerge(bcline)
gpd.GeoDataFrame({'name':['Outlet']},geometry=[bcline],crs=2272).to_file("bcline.gpkg")
# ---- points
base=60.0; fine=30.0
inner=keep.buffer(-0.6*base)
x0,y0,x1,y1=keep.bounds
xs=np.arange(np.floor(x0/base)*base+base/2,x1,base); ys=np.arange(np.floor(y0/base)*base+base/2,y1,base)
X,Y=np.meshgrid(xs,ys); pts=np.c_[X.ravel(),Y.ravel()]
import shapely
m=shapely.contains_xy(inner,pts[:,0],pts[:,1]); pts=pts[m]
# refinement around larger streams
up=np.load("up10.npy"); d10=rasterio.open("dem10_enf.tif")
big=[]
for g in st.geometry:
    if g.length<50: continue
    mid=g.interpolate(0.5,normalized=True); r,c=d10.index(mid.x,mid.y)
    da=float(up[max(r-3,0):r+4,max(c-3,0):c+4].max())*640
    if da>=300: big.append(g)
zone=shapely.union_all([g.buffer(60) for g in big]).intersection(keep.buffer(-0.6*base))
print("refine zone ac",zone.area/43560)
pts=pts[~shapely.contains_xy(zone.buffer(base*0.3),pts[:,0],pts[:,1])]
xs=np.arange(np.floor(x0/fine)*fine+fine/2,x1,fine); ys=np.arange(np.floor(y0/fine)*fine+fine/2,y1,fine)
X,Y=np.meshgrid(xs,ys); fp=np.c_[X.ravel(),Y.ravel()]
fp=fp[shapely.contains_xy(zone,fp[:,0],fp[:,1])]
pts=np.vstack([pts,fp])
nconn=0
# dedupe close points
tree=cKDTree(pts); pairs=tree.query_pairs(r=fine*0.35); drop=set(j for i,j in pairs)
pts=np.delete(pts,list(drop),axis=0)
pts=pts[shapely.contains_xy(keep.buffer(-0.5*fine),pts[:,0],pts[:,1])]
print("points",len(pts))
q=np.array([2572327,269982]); pts=pts[np.hypot(*(pts-q).T)>45]
np.save("mesh_points.npy",pts); 
