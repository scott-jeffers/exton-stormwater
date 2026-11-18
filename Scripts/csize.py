import numpy as np, geopandas as gpd, rasterio, pandas as pd, math
from shapely.geometry import LineString, Point
pd.set_option('display.width',250)
ds=rasterio.open("ValleyCk_DEM_1m_ft.tif"); A=ds.read(1); H,W=A.shape
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
g=gpd.read_file("culvert_candidates.gpkg").reset_index(drop=True)
def z(x,y):
    r,c=ds.index(x,y); 
    return float(A[r,c]) if 0<=r<H and 0<=c<W and A[r,c]>-9000 else np.nan
# Atlas 14 10-yr depths (in): 5,10,15,30,60,120 min
dur=np.array([5,10,15,30,60,120,180]); dep=np.array([0.537,0.858,1.08,1.57,2.05,2.48,2.70])
def i10(tc): return np.interp(np.log(tc),np.log(dur),np.log(dep/(dur/60)),) 
def Q10(da):
    def qr(a):
        tc=10+25*math.sqrt(a/640); return 0.39*math.exp(i10(tc))*a
    return qr(da) if da<=200 else qr(200)*(da/200)**0.6
pipes=[1.25,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6]
recs=[]
for i,r in g.iterrows():
    q=Q10(r.da_ac)
    seg=r.geometry; 
    crest_pt=Point(r.cx,r.cy)
    # local direction of flow near crest
    d=seg.project(crest_pt); p1=seg.interpolate(max(d-15,0)); p2=seg.interpolate(min(d+15,seg.length))
    vx,vy=p2.x-p1.x,p2.y-p1.y; L=math.hypot(vx,vy) or 1; vx,vy=vx/L,vy/L
    lx,ly=-vy,vx   # left of downstream direction
    crest_z=z(r.cx,r.cy)
    # extend along left/right until terrain rises 3 ft above crest or 150 ft
    half=[]
    for sgn in (1,-1):
        h=40
        for t in np.arange(10,151,5):
            zz=z(r.cx+sgn*lx*t,r.cy+sgn*ly*t)
            if np.isnan(zz) or zz>crest_z+3: break
            h=t
        half.append(max(h,40))
    s=(r.cx+lx*half[0],r.cy+ly*half[0]); e=(r.cx-lx*half[1],r.cy-ly*half[1])
    cl=LineString([s,e])
    us=r.us_inv; ds_=r.ds_inv
    if ds_>=us-0.05: ds_=us-max(0.005*r.length,0.1)
    hgt=crest_z-us
    maxrise=max(1.25,min(hgt-1.0,12))
    shape=1; rise=None; span=0; nb=1
    cap=lambda D: 2.36*D**2.5
    for D in pipes:
        if D<=maxrise and cap(D)>=q: rise=D; break
    if rise is None:
        D=max([p for p in pipes if p<=maxrise] or [1.25])
        nb=math.ceil(q/cap(D))
        if nb<=3 and r.da_ac<=500: rise=D
        else:
            shape=2; rise=min(math.floor(maxrise),10); rise=max(rise,2)
            B=q/(3.3*rise**1.5); nb=max(1,math.ceil(B/16)); span=max(3,math.ceil(B/nb))
            if span>16: span=16
    recs.append(dict(cid=f"C{i+1:03d}",shape=shape,rise=rise,span=span,barrels=nb,length=max(r.length,20),us_inv=round(us,2),ds_inv=round(ds_,2),
        crest=round(crest_z,2),q10_est=round(q,1),da_ac=round(r.da_ac,1),src=r.src,stream=r.stream,road=r.road,conn_half_l=half[0],conn_half_r=half[1],geometry=cl,
        seg_wkt=seg.wkt))
c=gpd.GeoDataFrame(recs,crs=2272)
# drop connection lines that cross perimeter or each other
P=ws.buffer(-40)
c=c[c.geometry.within(P)]
bad=set()
for i in range(len(c)):
    for j in range(i+1,len(c)):
        if c.geometry.iloc[i].distance(c.geometry.iloc[j])<70:
            # keep larger DA
            bad.add(c.index[j] if c.da_ac.iloc[i]>=c.da_ac.iloc[j] else c.index[i])
c=c.drop(index=list(bad))
print(len(c)); print(c.groupby(['shape']).size()); 
print(c[['cid','shape','rise','span','barrels','length','us_inv','ds_inv','crest','q10_est','da_ac','road']].sort_values('da_ac',ascending=False).head(20).to_string())
c.to_file("culverts_final.gpkg")
