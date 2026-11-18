import numpy as np, geopandas as gpd, shapely
from scipy.spatial import cKDTree
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
cu=gpd.read_file("culverts_model_in.gpkg")
pts=np.load("mesh_points.npy")
# dedupe <5 ft
T=cKDTree(pts); pr=T.query_pairs(5.0); drop=set(j for i,j in pr); pts=np.delete(pts,list(drop),axis=0); print("dup removed",len(drop))
x0,y0,x1,y1=per.bounds
g=np.mgrid[x0:x1:30,y0:y1:30].reshape(2,-1).T
g=g[shapely.contains_xy(per.buffer(-36),g[:,0],g[:,1])]
d,_=cKDTree(pts).query(g)
cand=g[d>55]
conn=gpd.read_file('conn_zones.gpkg').geometry.iloc[0].buffer(10)
cand=cand[~shapely.contains_xy(conn,cand[:,0],cand[:,1])]
# thin candidates
keep=[]
for c in cand:
    if all(np.hypot(*(c-k))>50 for k in keep[-200:]): keep.append(c)
print("fill pts",len(keep))
if keep: pts=np.vstack([pts,np.array(keep)])
np.save("mesh_points.npy",pts); print(len(pts))
