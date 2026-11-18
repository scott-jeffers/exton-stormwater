import numpy as np, geopandas as gpd, shapely, networkx as nx
from scipy.spatial import Voronoi, cKDTree
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
pts=np.load("mesh_points.npy"); cu=gpd.read_file("culverts_model_in.gpkg")
vor=Voronoi(pts)
V=vor.vertices; G=nx.Graph()
for (a,b) in vor.ridge_vertices:
    if a>=0 and b>=0: G.add_edge(a,b,w=float(np.hypot(*(V[a]-V[b]))))
T=cKDTree(V); bad=[]
for r in cu.itertuples():
    g=r.geometry; s=g.coords[0]; e=g.coords[-1]
    _,i=T.query(s); _,j=T.query(e)
    try: L=nx.shortest_path_length(G,i,j,weight='w')
    except Exception: L=1e9
    ratio=L/g.length
    if ratio>1.6: bad.append((r.cid,round(ratio,2),round(np.hypot(*(V[i]-s)),1),round(np.hypot(*(V[j]-e)),1)))
print(len(bad),bad[:20])
