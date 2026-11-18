import numpy as np, geopandas as gpd, shapely
from shapely import voronoi_polygons, MultiPoint
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
pts=np.load("mesh_points.npy")
for it in range(3):
    mp=shapely.multipoints(pts)
    vor=voronoi_polygons(mp,extend_to=per.buffer(500))
    cells=list(vor.geoms)
    # map cells to points
    tree=shapely.STRtree(cells)
    P=shapely.points(pts)
    idx=tree.query(P,predicate="within")
    cell_of=np.full(len(pts),-1); cell_of[idx[0]]=idx[1]
    bad=[]
    for i,c in enumerate(cell_of):
        cc=cells[c].intersection(per)
        if cc.is_empty or cc.geom_type!="Polygon" or cc.area<150 or not cc.contains(P[i]): bad.append(i)
    print("iter",it,"bad",len(bad), [tuple(pts[b].round()) for b in bad[:10]])
    if not bad: break
    pts=np.delete(pts,bad,axis=0)
np.save("mesh_points.npy",pts); print(len(pts))
