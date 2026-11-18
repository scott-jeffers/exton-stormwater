import geopandas as gpd, numpy as np, pandas as pd, shapely
nodes=gpd.read_file("pipe_nodes.gpkg"); pf=gpd.read_file("pipe_links.gpkg")
cu=gpd.read_file("culverts_model.gpkg")
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
# drop pipes that duplicate lidar culverts (cross a connection line)
cl=shapely.union_all(list(cu.geometry))
dup=pf.geometry.intersects(cl.buffer(10))
print("pipes",len(pf),"dup w/ culverts",dup.sum())
pf=pf[~dup]
# keep pipes fully inside 2D perimeter
pf=pf[pf.geometry.within(per.buffer(-20))]
used=set(pf.up)|set(pf.dn); nodes=nodes[nodes.nid.isin(used)].copy()
# node invert = min connected pipe inverts
inv={}
for r in pf.itertuples():
    inv[r.up]=min(inv.get(r.up,1e9),r.up_inv); inv[r.dn]=min(inv.get(r.dn,1e9),r.dn_inv)
nodes['invert']=nodes.nid.map(inv)
nodes['rim']=np.maximum(nodes.rim,nodes.invert+pf.groupby('up').D.max().reindex(nodes.nid).fillna(1.25).values+0.5)
# terminal nodes (no outgoing) are outfalls
outs=set(pf.dn)-set(pf.up); nodes['is_out']=nodes.nid.isin(outs)
name=lambda n: f"N{n:05d}"
L=["[TITLE]","Valley Creek (Exton PA) storm sewer - INFERRED inverts/sizes from lidar + county GIS (no survey)","",
"[OPTIONS]","FLOW_UNITS CFS","INFILTRATION HORTON","FLOW_ROUTING DYNWAVE","START_DATE 01/01/2026","START_TIME 00:00:00","END_DATE 01/01/2026","END_TIME 18:00:00","ROUTING_STEP 0:00:05","",
"[JUNCTIONS]",";;Name Elevation MaxDepth InitDepth SurDepth Aponded"]
for r in nodes[~nodes.is_out].itertuples(): L.append(f"{name(r.nid)} {r.invert:.2f} {r.rim-r.invert:.2f} 0 0 0")
L+=["","[OUTFALLS]",";;Name Elevation Type StageData Gated"]
for r in nodes[nodes.is_out].itertuples(): L.append(f"{name(r.nid)} {r.invert:.2f} FREE NO")
L+=["","[CONDUITS]",";;Name From To Length Roughness InOffset OutOffset InitFlow MaxFlow"]
X=["","[XSECTIONS]",";;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels"]
V=["","[VERTICES]",";;Link X Y"]
for i,r in enumerate(pf.itertuples()):
    nm=f"P{i+1:05d}"
    L.append(f"{nm} {name(r.up)} {name(r.dn)} {max(r.L,1):.1f} 0.013 {r.up_inv-inv[r.up]:.2f} {r.dn_inv-inv[r.dn]:.2f} 0 0")
    X.append(f"{nm} CIRCULAR {r.D:.3f} 0 0 0 1")
    for x,y in list(r.geometry.coords)[1:-1]: V.append(f"{nm} {x:.2f} {y:.2f}")
L+=X+["","[COORDINATES]",";;Node X Y"]+[f"{name(r.nid)} {r.geometry.x:.2f} {r.geometry.y:.2f}" for r in nodes.itertuples()]+V
open("proj/ValleyCreek/GIS/StormSewer_Inferred.inp","w").write("\n".join(L)+"\n")
nodes['name']=nodes.nid.map(name); nodes.drop(columns=['nid']).to_file("proj/ValleyCreek/GIS/StormSewer_Nodes_Inferred.shp")
pf2=pf.copy(); pf2['name']=[f"P{i+1:05d}" for i in range(len(pf2))]; pf2['up_node']=pf2.up.map(name); pf2['dn_node']=pf2.dn.map(name); pf2['dia_in']=pf2.D*12
pf2[['name','up_node','dn_node','L','dia_in','up_inv','dn_inv','slope','cover_up','Q10','acc_ac','dia_src','inv_src','qa','geometry']].rename(columns={'acc_ac':'da_ac_est'}).to_file("proj/ValleyCreek/GIS/StormSewer_Pipes_Inferred.shp")
print("pipes kept",len(pf),"nodes",len(nodes),"outfalls",nodes.is_out.sum(), "total mi",pf.L.sum()/5280)
