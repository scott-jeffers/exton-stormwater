# Hydro-enforce stream network on a DEM: monotonic-descending profiles along digitized streams
import numpy as np, geopandas as gpd, rasterio, sys, collections
from rasterio.features import rasterize
dem_path, out_path, step = sys.argv[1], sys.argv[2], float(sys.argv[3])
ds=rasterio.open(dem_path); a=ds.read(1).astype(np.float32); nod=ds.nodata
st=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Rivers_and_Streams",bbox=tuple(ds.bounds)).explode(index_parts=False).reset_index(drop=True)
st=st[st.length>0]
# topological order via junctions
inc=collections.defaultdict(list); 
for i,(jf,jt) in enumerate(zip(st.JUNCTION_F,st.JUNCTION_T)): inc[jt].append(i)
indeg={i:len(inc[jf]) for i,jf in enumerate(st.JUNCTION_F)}
endval={}
order=[]; q=collections.deque([i for i,d in indeg.items() if d==0]); 
down=collections.defaultdict(list)
for i,jf in enumerate(st.JUNCTION_F):
    for u in inc[jf]: down[u].append(i)
seen=set()
while q:
    i=q.popleft(); 
    if i in seen: continue
    seen.add(i); order.append(i)
    for d in down[i]:
        indeg[d]-=1
        if indeg[d]<=0: q.append(d)
order+= [i for i in range(len(st)) if i not in seen]
H,W=a.shape; out=a.copy(); cut=np.zeros_like(a)
geoms=st.geometry.values; jf=st.JUNCTION_F.values
recs=[]
for i in order:
    g=geoms[i]; n=max(2,int(g.length/step)+1)
    pts=[g.interpolate(t) for t in np.linspace(0,g.length,n)]
    rc=[ds.index(p.x,p.y) for p in pts]
    z=np.array([a[r,c] if 0<=r<H and 0<=c<W else np.nan for r,c in rc],dtype=float)
    z[z==nod]=np.nan
    start=[endval[u] for u in inc[jf[i]] if u in endval]
    z0=np.nanmin([z[0]]+start) if len(start) else z[0]
    z[0]=z0 if not np.isnan(z0) else z[0]
    zz=np.fmin.accumulate(np.where(np.isnan(z),np.inf,z))
    endval[i]=zz[-1]
    for (r,c),v,v0 in zip(rc,zz,z):
        if 0<=r<H and 0<=c<W and np.isfinite(v):
            nv=v-0.5
            if nv<out[r,c]:
                cut[r,c]=max(cut[r,c],a[r,c]-nv); out[r,c]=nv
prof=ds.profile; prof.update(dtype="float32")
with rasterio.open(out_path,"w",**prof) as o: o.write(out,1)
with rasterio.open(out_path.replace(".tif","_cut.tif"),"w",**prof) as o: o.write(cut,1)
print("segments",len(st),"cells cut >5ft",(cut>5).sum())
