import numpy as np, geopandas as gpd, pandas as pd, rasterio, networkx as nx, math, collections
from scipy.spatial import cKDTree
from scipy.ndimage import minimum_filter
from shapely.geometry import Point, LineString
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
gm=gpd.read_file("sw/GravityMain_clean.gpkg").explode(index_parts=False).reset_index(drop=True)
gm=gm[gm.length>1].reset_index(drop=True)
inl=gpd.read_file("sw/Inlet.gpkg"); mh=gpd.read_file("sw/Manholes.gpkg"); dp=gpd.read_file("sw/DischargePoint.gpkg")
dem=rasterio.open("ValleyCk_DEM_1m_ft.tif"); A=dem.read(1)
def z(x,y,r=0):
    rr,cc=dem.index(x,y); w=A[max(rr-r,0):rr+r+1,max(cc-r,0):cc+r+1]; w=w[w>-9000]
    return float(w.min()) if len(w) else np.nan
# --- nodes from pipe endpoints (snap 1.0 ft)
E=[];
for g in gm.geometry: E+=[g.coords[0][:2],g.coords[-1][:2]]
E=np.array(E); T=cKDTree(E); groups=T.query_ball_point(E,1.0)
nid=-np.ones(len(E),int); k=0
for i,gp in enumerate(groups):
    if nid[i]<0:
        for j in gp: nid[j]=k
        k+=1
nxy=np.array([E[nid==i].mean(axis=0) for i in range(k)])
# structure typing
def nearest(gdf):
    t=cKDTree(np.c_[gdf.geometry.x,gdf.geometry.y]); d,i=t.query(nxy); return d,i
di,ii=nearest(inl); dm,im=nearest(mh); dd,id_=nearest(dp)
ntype=np.where(dd<3,"Outfall",np.where(di<3,"Inlet",np.where(dm<3,"Manhole","Junction")))
ndia=np.where(dd<3,dp.DIAMETER.values[id_]/12.0,np.nan); ndia[ndia<=0]=np.nan
rim=np.array([z(x,y,1) for x,y in nxy])
mhrim=np.where((dm<3)&(mh.RIMELEV.fillna(0).values[im]>100),mh.RIMELEV.fillna(0).values[im],np.nan)
print("nodes",k,collections.Counter(ntype)); print("manhole rim vs lidar diff:",np.nanpercentile(mhrim-rim,[10,50,90]).round(2))
# graph
G=nx.Graph()
for p,g in enumerate(gm.geometry): G.add_edge(nid[2*p],nid[2*p+1],pid=p,L=g.length)
comps=list(nx.connected_components(G)); print("components",len(comps))
# outlets per component
outlets=set()
deg=dict(G.degree())
for c in comps:
    o=[n for n in c if ntype[n]=="Outfall"]
    if not o:
        ends=[n for n in c if deg[n]==1] or list(c)
        o=[min(ends,key=lambda n:rim[n])]
    outlets.update(o)
dist=nx.multi_source_dijkstra_path_length(G,outlets,weight="L")
# orient pipes: from far to near
D=nx.DiGraph()
for u,v,d in G.edges(data=True):
    a,b=(u,v) if dist[u]>=dist[v] else (v,u)
    D.add_edge(a,b,**d)
# break cycles if any by removing edges with smallest dist difference
while not nx.is_directed_acyclic_graph(D):
    cyc=nx.find_cycle(D); D.remove_edge(*cyc[0][:2])
order=list(nx.topological_sort(D))
# drainage area proxy: inlets upstream (0.6 ac each) + 0.4 ac per manhole
loc={n:(0.6 if ntype[n]=="Inlet" else 0.3) for n in D.nodes}
acc={}
for n in order:
    acc[n]=loc[n]+sum(acc[u] for u in D.predecessors(n))
std=[1.25,1.5,1.75,2,2.5,3,3.5,4,4.5,5,5.5,6,7,8]
dep=np.array([0.537,0.858,1.08,1.57,2.05,2.48]); dur=np.array([5,10,15,30,60,120])
def i10(tc): return float(np.exp(np.interp(np.log(tc),np.log(dur),np.log(dep/(dur/60)))))
# path length upstream for tc
upL={}
for n in order: upL[n]=max([upL[u]+D[u][n]['L'] for u in D.predecessors(n)] or [0])
Smin=0.005; cover=1.5; n_man=0.013
inv_out={}  # invert at node outlet
pipe=[]
nodeinv={}
for n in order:
    ins=[(u,D[u][n]) for u in D.predecessors(n)]
    outs=list(D.successors(n))
    for v in outs:
        d=D[n][v]; L=d['L']
        a=acc[n]; tc=10+upL[n]/(3*60)  # 3 fps pipe flow
        Q=0.6*i10(tc)*a
        zs=(rim[n]-rim[v])/L if L>0 else 0
        S=max(Smin,min(zs,0.08))
        Dr=(Q*n_man/(0.463*S**0.5))**0.375
        Dp=next((s for s in std if s>=Dr),8.0)
        # non-decreasing downstream: at least max of incoming
        Dp=max([Dp]+[pp['D'] for pp in pipe if pp['dn']==n])
        up_inv_cover=rim[n]-cover-Dp
        up_inv=min([up_inv_cover]+[pp['dn_inv']-0.0 for pp in pipe if pp['dn']==n]) if ins else up_inv_cover
        # crown alignment with incoming pipes: invert drop so crowns match
        if ins: up_inv=min(up_inv, min(pp['dn_inv']+pp['D']-Dp for pp in pipe if pp['dn']==n))
        dn_inv=min(up_inv-S*L, rim[v]-cover-Dp)
        pipe.append(dict(pid=d['pid'],up=n,dn=v,L=L,D=Dp,Q10=Q,acc_ac=a,up_inv=up_inv,dn_inv=dn_inv))
    nodeinv[n]=min([p['up_inv'] for p in pipe if p['up']==n]+[p['dn_inv'] for p in pipe if p['dn']==n] or [rim[n]-4])
pf=pd.DataFrame(pipe)
# outfalls: daylight into channel. invert >= channel bottom (min lidar within 15 ft) - 1 ft
for o in outlets:
    g0=z(*nxy[o],4)
    m=pf.dn==o
    if m.any(): pf.loc[m,'dn_inv']=np.maximum(pf.loc[m,'dn_inv'],g0-1.0)
# backward pass: positive slope >=0.1%, but never push crown above rim-0.5 ft (then accept 0.05%)
for n in reversed(order):
    outs=pf.index[pf.up==n]
    if len(outs):
        lo=pf.loc[outs,'up_inv'].min()
        for idx in pf.index[pf.dn==n]:
            if pf.at[idx,'dn_inv']<lo: pf.at[idx,'dn_inv']=lo
    for idx in pf.index[pf.dn==n]:
        pass
for idx in pf.index:
    need=pf.at[idx,'dn_inv']+0.001*pf.at[idx,'L']
    if pf.at[idx,'up_inv']<need:
        cap=rim[pf.at[idx,'up']]-0.5-pf.at[idx,'D']
        pf.at[idx,'up_inv']=max(min(need,cap),pf.at[idx,'dn_inv']+0.0005*pf.at[idx,'L'])
# known outfall diameters: cap terminal pipe size to recorded, and use it
pf['dia_src']='inferred (Rational Q10 + Manning full-flow)'
gd=gm.DIAMETER.fillna(0).values
for i,p in enumerate(pf.pid):
    if gd[p]>=12: pf.at[i,'D']=gd[p]/12; pf.at[i,'dia_src']='county GIS'
for o in outlets:
    if not np.isnan(ndia[o]) and ndia[o]>=1.0:
        m=pf.dn==o; pf.loc[m,'D']=ndia[o]; pf.loc[m,'dia_src']='outfall GIS diameter'
pf['inv_src']='inferred (lidar rim - cover, min slope)'
ninv={}
for n in D.nodes:
    v=[pf.up_inv[pf.up==n].min(), pf.dn_inv[pf.dn==n].min()]
    ninv[n]=np.nanmin(v)
pf['cover_up']=[rim[u]-(iu+d) for u,iu,d in zip(pf.up,pf.up_inv,pf.D)]
print(pf.D.value_counts().sort_index()); print("cover pct",np.percentile(pf.cover_up,[1,5,50,95]).round(2))
print("slope pct",np.percentile((pf.up_inv-pf.dn_inv)/pf.L,[1,5,50,95]).round(4))
nodes=gpd.GeoDataFrame(dict(nid=range(k),ntype=ntype,rim=rim,invert=[ninv.get(i,np.nan) for i in range(k)],outlet=[i in outlets for i in range(k)],
     known_dia_in=ndia*12),geometry=[Point(x,y) for x,y in nxy],crs=2272)
pf['geometry']=[gm.geometry[p] if dist[nid[2*p]]>=dist[nid[2*p+1]] else LineString(list(gm.geometry[p].coords)[::-1]) for p in pf.pid]
pf=gpd.GeoDataFrame(pf,crs=2272)
nodes.to_file("pipe_nodes.gpkg"); pf.to_file("pipe_links.gpkg")
print("outlets",len(outlets),"of which mapped outfalls",sum(ntype[o]=="Outfall" for o in outlets))
