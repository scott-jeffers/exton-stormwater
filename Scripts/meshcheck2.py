import numpy as np, geopandas as gpd, shapely
from shapely import voronoi_polygons
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
pts=np.load("mesh_points.npy"); ap=np.load('conn_points.npy')
from scipy.spatial import cKDTree
prot=np.zeros(len(pts),bool); dd,_=cKDTree(ap).query(pts); prot[dd<0.01]=True
for it in range(12):
    vor=voronoi_polygons(shapely.multipoints(pts),extend_to=per.buffer(500))
    cells=list(vor.geoms); tree=shapely.STRtree(cells); P=shapely.points(pts)
    idx=tree.query(P,predicate="within"); cell_of=np.full(len(pts),-1); cell_of[idx[0]]=idx[1]
    bad=[]
    for i,c in enumerate(cell_of):
        cc=cells[c].intersection(per)
        if cc.is_empty or cc.geom_type!="Polygon" or cc.area<150 or not cc.contains(P[i]): bad.append(i); continue
        co=np.array(cc.exterior.coords); L=np.hypot(*np.diff(co,axis=0).T)
        # RAS merges faces shorter than ~5% of cell size
        if (L>0.05*np.sqrt(cc.area)).sum()>7: bad.append(i)
    print("iter",it,"bad",len(bad))
    if not bad: break
    T=cKDTree(pts); rm=set()
    for b in bad:
        if not prot[b]: rm.add(b); continue
        dd,nn=T.query(pts[b],k=8)
        for n in nn[1:]:
            if not prot[n]: rm.add(n); break
    rm=sorted(rm); pts=np.delete(pts,rm,axis=0); prot=np.delete(prot,rm)
np.save("mesh_points.npy",pts); print(len(pts))
