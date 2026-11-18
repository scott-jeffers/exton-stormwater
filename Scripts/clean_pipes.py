import geopandas as gpd, numpy as np, shapely
from shapely.geometry import LineString, Point
from scipy.spatial import cKDTree
gm=gpd.read_file("sw/GravityMain.gpkg").explode(index_parts=False).reset_index(drop=True)
gm=gm[gm.length>=3].reset_index(drop=True)
inl=gpd.read_file("sw/Inlet.gpkg"); mh=gpd.read_file("sw/Manholes.gpkg"); dp=gpd.read_file("sw/DischargePoint.gpkg")
S=np.vstack([np.c_[d.geometry.x,d.geometry.y] for d in (inl,mh,dp)])
TS=cKDTree(S)
coords=[list(g.coords) for g in gm.geometry]
log=[]
def ends():
    return np.array([c for cs in coords for c in (cs[0][:2],cs[-1][:2])])
E=ends(); TE=cKDTree(E)
fix_struct=fix_end=fix_t=0
for k in range(len(E)):
    p=E[k]; pi,end=k//2,k%2
    ds,si=TS.query(p)
    dd,ei=TE.query(p,k=2); de,ej=dd[1],ei[1]
    if ds<=2 or de<=2: 
        if 0.01<ds<=2: q=S[si]
        else: continue
    elif ds<=30:  q=S[si]; fix_struct+=1; log.append(("snap_to_structure",pi,round(ds,1)))
    elif de<=15:  q=E[ej]; fix_end+=1; log.append(("snap_to_pipe_end",pi,round(de,1)))
    else: continue
    cs=coords[pi]
    if end==0: cs[0]=(q[0],q[1])
    else: cs[-1]=(q[0],q[1])
# T-junctions: dangling end within 1 ft of another pipe interior -> split that pipe
E=ends(); TE=cKDTree(E); out=[LineString(c) for c in coords]
gs=gpd.GeoSeries(out); sidx=gs.sindex
splits={}
for k in range(len(E)):
    p=Point(E[k]); ds,_=TS.query(E[k]); dd,_=TE.query(E[k],k=2)
    if ds<=2 or dd[1]<=2: continue
    for c in sidx.query(p.buffer(2)):
        if c==k//2: continue
        if gs[c].distance(p)<2:
            t=gs[c].project(p)
            if 3<t<gs[c].length-3: splits.setdefault(c,[]).append((t,E[k])); fix_t+=1; log.append(("split_T",c,round(t,1)))
new=[];attrs=[]
for i,g in enumerate(out):
    if i in splits:
        ts=sorted(splits[i]); prev=0
        for t,pt in ts:
            seg=shapely.ops.substring(g,prev,t); cs=list(seg.coords); cs[-1]=tuple(pt); new.append(LineString(cs)); attrs.append(i); prev=t
        seg=shapely.ops.substring(g,prev,g.length); cs=list(seg.coords); cs[0]=tuple(ts[-1][1]); new.append(LineString(cs)); attrs.append(i)
    else: new.append(g); attrs.append(i)
cl=gm.iloc[attrs].copy().reset_index(drop=True); cl['geometry']=new; cl=gpd.GeoDataFrame(cl,crs=2272)
cl=cl[cl.length>=3]
# drop exact duplicates
key=cl.geometry.apply(lambda g: tuple(sorted([tuple(np.round(g.coords[0][:2],1)),tuple(np.round(g.coords[-1][:2],1))])))
dup=key.duplicated(); cl=cl[~dup]
cl.to_file("sw/GravityMain_clean.gpkg")
import pandas as pd
pd.DataFrame(log,columns=["fix","pipe_idx","value_ft"]).to_csv("sw/pipe_cleanup_log.csv",index=False)
print("snap->structure",fix_struct,"snap->pipe end",fix_end,"T splits",fix_t,"dups removed",int(dup.sum()),"pipes",len(cl))
