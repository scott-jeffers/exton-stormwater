import numpy as np, geopandas as gpd, rasterio, shapely, shapely.wkt, math
from rasterio.windows import from_bounds
from shapely.geometry import LineString
src=rasterio.open("ValleyCk_DEM_1m_ft_hydro.tif"); A=src.read(1); T=src.transform
c=gpd.read_file("culverts_model.gpkg")
n=0
for _,r in c.iterrows():
    seg=shapely.wkt.loads(r.seg_wkt)
    co=list(seg.coords); p0=np.array(co[0][:2]); p1=np.array(co[-1][:2])
    # extend 10 ft each end
    u0=p0-np.array(co[1][:2]); u0/=np.linalg.norm(u0)+1e-9; u1=p1-np.array(co[-2][:2]); u1/=np.linalg.norm(u1)+1e-9
    line=LineString([tuple(p0+u0*10)]+[c_[:2] for c_ in co]+[tuple(p1+u1*10)])
    w_open=r.barrels*((r.span if r['shape']==2 else r.rise))+max(0,r.barrels-1)*1.0
    b=max(3.0,w_open)
    ext=line.buffer(b/2+15)
    win=from_bounds(*ext.bounds,T).round_offsets().round_lengths()
    r0,c0=int(win.row_off),int(win.col_off); h,w=int(win.height),int(win.width)
    if r0<0 or c0<0: continue
    sub=A[r0:r0+h,c0:c0+w]
    rows,cols=np.indices(sub.shape)
    P=shapely.points(T.c+(c0+cols.ravel()+0.5)*T.a, T.f+(r0+rows.ravel()+0.5)*T.e)
    dd=shapely.distance(P,line).reshape(sub.shape); tt=(shapely.line_locate_point(line,P)/line.length).reshape(sub.shape)
    prof=r.us_inv+(r.ds_inv-r.us_inv)*tt
    newz=np.where(dd<=b/2,prof,prof+(dd-b/2)*1.0)
    m=(dd<=b/2+15)&(sub>-9000)
    sub[m]=np.minimum(sub[m],newz[m]).astype(np.float32)
    A[r0:r0+h,c0:c0+w]=sub; n+=1
with rasterio.open("ValleyCk_DEM_1m_ft_hydro_v2.tif","w",**src.profile) as o: o.write(A,1)
print("burned",n)
