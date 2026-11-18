import numpy as np, geopandas as gpd, rasterio, shapely.wkt, math
from rasterio.windows import from_bounds
from rasterio.features import rasterize
c=gpd.read_file("culverts_final.gpkg")
cand=gpd.read_file("culvert_candidates.gpkg")
relief_of={}
c['seg']=c.seg_wkt.apply(shapely.wkt.loads)
c['relief']=c.crest-c.us_inv
isbr=(c.da_ac>=640)&(c.relief<10)&(c['length']<150)
br=c[isbr].copy(); cu=c[~isbr].copy()
print("bridges",len(br),"culverts",len(cu))
src=rasterio.open("ValleyCk_DEM_1m_ft.tif"); A=src.read(1); T=src.transform
for _,r in br.iterrows():
    seg=r.seg; ext=seg.buffer(80)
    b=max(10,12*math.sqrt(r.da_ac/640))
    w=from_bounds(*ext.bounds,T); w=w.round_offsets().round_lengths()
    r0,c0=int(w.row_off),int(w.col_off); sub=A[r0:r0+int(w.height),c0:c0+int(w.width)]
    rows,cols=np.indices(sub.shape)
    xs=T.c+(c0+cols+0.5)*T.a; ys=T.f+(r0+rows+0.5)*T.e
    from shapely import points, distance, line_locate_point
    P=points(xs.ravel(),ys.ravel())
    dd=distance(P,seg).reshape(sub.shape); tt=line_locate_point(seg,P).reshape(sub.shape)/seg.length
    prof=r.us_inv+(r.ds_inv-r.us_inv)*tt
    newz=np.where(dd<=b/2,prof,prof+(dd-b/2)*1.0)
    m=(dd<=b/2+15)&(sub>-9000)
    sub[m]=np.minimum(sub[m],newz[m])
    A[r0:r0+int(w.height),c0:c0+int(w.width)]=sub
prof=src.profile
with rasterio.open("ValleyCk_DEM_1m_ft_hydro.tif","w",**prof) as o: o.write(A,1)
br=br.drop(columns=['seg']); br['geometry']=gpd.GeoSeries.from_wkt(br.seg_wkt); br['bottom_w']=[max(10,12*math.sqrt(d/640)) for d in br.da_ac]
br.drop(columns=['seg_wkt']).set_crs(2272,allow_override=True).to_file("bridge_openings.gpkg")
cu=cu.drop(columns=['seg']).reset_index(drop=True)
cu['cid']=[f"C{i+1:03d}" for i in range(len(cu))]
cu.to_file("culverts_model.gpkg")
print(cu.groupby('shape').size(), cu.barrels.value_counts())
