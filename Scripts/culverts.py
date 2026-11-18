import numpy as np, geopandas as gpd, rasterio, pandas as pd
from scipy.ndimage import minimum_filter
from shapely.geometry import Point, LineString
ds=rasterio.open("ValleyCk_DEM_1m_ft.tif"); A=ds.read(1); H,W=A.shape
A[A==-9999]=np.nan
Amin=minimum_filter(np.nan_to_num(A,nan=1e4),size=5)
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
st=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Rivers_and_Streams",mask=ws).explode(index_parts=False)
st=st[st.length>5][['NAME','HIDDEN','geometry']]; st['src']='county_stream'
fl=gpd.read_file("flowlines.gpkg"); 
near=fl.geometry.apply(lambda g: g.buffer(1).intersection(st.buffer(40).union_all()).area/ max(g.buffer(1).area,1))
fl=fl[near<0.5].copy(); fl['NAME']='DEM flow path'; fl['HIDDEN']=''; fl['src']='dem_flowpath'
lines=pd.concat([st,fl[['NAME','HIDDEN','src','geometry']]],ignore_index=True)
roads=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Roads",mask=ws.buffer(200))
rsi=roads.sindex
up=np.load("up10.npy"); d10=rasterio.open("dem10_enf.tif")
step=1.5
recs=[]
def zs(pts):
    out=[]
    for p in pts:
        r,c=ds.index(p.x,p.y)
        out.append(Amin[r,c] if 0<=r<H and 0<=c<W and Amin[r,c]<1e4 else np.nan)
    return np.array(out)
for li,(name,hid,src,g) in enumerate(lines[['NAME','HIDDEN','src','geometry']].itertuples(index=False)):
    if g.geom_type!="LineString": continue
    n=int(g.length/step)+1
    if n<8: continue
    d=np.linspace(0,g.length,n); pts=[g.interpolate(t) for t in d]
    z=zs(pts)
    if np.isnan(z).mean()>0.2: continue
    z=pd.Series(z).interpolate(limit_direction='both').values
    zc=np.minimum.accumulate(z)
    ex=z-zc
    blocked=ex>1.0
    i=0
    while i<n:
        if not blocked[i]: i+=1; continue
        s=i
        while i<n and blocked[i]: i+=1
        e=min(i,n-1)
        s0=max(s-1,0)
        crest=z[s:e+1].max()
        k=max(1,int(30/step))
        zus=np.median(z[max(0,s0-k):s0+1]); zds=np.median(z[e:min(n,e+k)])
        relief=crest-max(zus,zds)
        L=d[e]-d[s0]
        if relief>=3.0 and 12<=L:
            p_up=pts[s0]; p_dn=pts[e]; pc=pts[s+int(np.argmax(z[s:e+1]))]
            rr,cc=d10.index(p_up.x,p_up.y); w=up[max(rr-3,0):rr+4,max(cc-3,0):cc+4]
            da=float(w.max())*640  # acres
            seg=LineString([(q.x,q.y) for q in pts[s0:e+1]])
            hit=list(rsi.query(seg.buffer(25)))
            rname=roads.iloc[hit[0]].RD_NAME_FULL if hit else None
            recs.append(dict(src=src,stream=name,hidden=hid,us_inv=float(zc[s0]),ds_inv=float(min(z[e],zc[s0])),crest=float(crest),
                relief=float(relief),length=float(L),da_ac=da,road=rname,us_x=p_up.x,us_y=p_up.y,ds_x=p_dn.x,ds_y=p_dn.y,cx=pc.x,cy=pc.y,geometry=seg))
gdf=gpd.GeoDataFrame(recs,crs=2272)
print(len(gdf)); print(gdf.groupby('src').size())
print(gdf.describe()[['relief','length','da_ac']].round(1))
gdf.to_file("culvert_candidates_raw.gpkg")
