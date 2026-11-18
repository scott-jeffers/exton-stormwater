import numpy as np, geopandas as gpd, rasterio, h5py, uuid
from rasterio.features import rasterize
from rasterio.transform import from_origin
P="proj/ValleyCreek/"
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
l,b,r,t=ws.buffer(600).bounds; cs=5.0
l=np.floor(l/10)*10; t=np.ceil(t/10)*10; W=int(np.ceil((r-l)/cs)); H=int(np.ceil((t-b)/cs)); tr=from_origin(l,t,cs,cs)
wkt=open("/dev/stdin").read() if False else None
prj=gpd.GeoSeries([],crs=2272).crs.to_wkt("WKT1_ESRI")
# --- land cover classes: id, name, n, %imp
LC=[(0,"NoData",0.06,0.),(1,"Building",0.40,100.),(2,"Road",0.016,100.),(3,"Pavement-Other",0.016,100.),
    (10,"Residential Pervious",0.045,0.),(11,"Commercial-Industrial Pervious",0.04,0.),(12,"Transportation-Utility Pervious",0.04,0.),
    (13,"Community-Recreation Pervious",0.035,0.),(14,"Agriculture",0.045,0.),(15,"Wooded",0.12,0.),(16,"Vacant-Meadow",0.06,0.),
    (17,"Mining-Quarry",0.035,0.),(18,"Water",0.035,100.),(19,"Parking (LU)",0.016,100.)]
lumap={"01000":10,"02000":10,"02020":10,"03000":11,"03010":11,"06000":11,"04000":12,"05000":12,"07000":13,"09000":13,"10000":14,"12000":15,"12010":16,"11000":17,"13000":18}
lu=gpd.read_file("lulc.gpkg")
lu['id']=[19 if t.endswith("009") else lumap.get(t,16) for t in lu.LU_TYPE]
arr=rasterize(((g,i) for g,i in zip(lu.geometry,lu.id)),out_shape=(H,W),transform=tr,fill=16,dtype="int32")
imp=gpd.read_file("imperv.gpkg"); im={"Building":1,"Road":2,"Other":3}
imp['id']=imp.CLASS.map(im).fillna(3).astype(int)
for cid in (3,2,1):
    sub=imp[imp.id==cid]
    m=rasterize(((g,1) for g in sub.geometry),out_shape=(H,W),transform=tr,fill=0,dtype="uint8")
    arr[m==1]=cid
prof=dict(driver="GTiff",width=W,height=H,count=1,dtype="int32",crs="EPSG:2272",transform=tr,tiled=True,blockxsize=256,blockysize=256,compress="deflate")
with rasterio.open(P+"Land Classification/LandCover.tif","w",**prof) as o: o.write(arr,1)
u,cnt=np.unique(arr,return_counts=True); print(dict(zip(u,np.round(cnt/cnt.sum()*100,1))))
def lchdf(path,lctype,rmap,variables=None,vdtype=None):
    with h5py.File(path,"w") as f:
        f.attrs["File Type"]=np.bytes_("HEC Land Cover"); f.attrs["GUID"]=np.bytes_(str(uuid.uuid4()))
        f.attrs["LC Type"]=np.bytes_(lctype); f.attrs["Projection"]=np.bytes_(prj); f.attrs["Version"]=np.bytes_("2.0")
        n=max(len(x[1]) for x in rmap)+1
        f.create_dataset("Raster Map",data=np.array(rmap,dtype=[("ID","<i4"),("Name",f"S{n}")]))
        if variables is not None: f.create_dataset("Variables",data=np.array(variables,dtype=vdtype))
nl=max(len(x[1]) for x in LC)+1
lchdf(P+"Land Classification/LandCover.hdf","LandCover",[(i,n) for i,n,_,_ in LC],[(n,nn,pi) for _,n,nn,pi in LC],[("Name",f"S{nl}"),("ManningsN","<f4"),("Percent Impervious","<f4")])
# --- soils
so=gpd.read_file("soils.gpkg")
def hsg(h,name):
    if h in ("A","B","C","D"): return h
    if isinstance(h,str) and "/" in h: return "D"
    nm=(name or "").lower()
    if "water" in nm: return "D"
    return "C"
so['g']=[hsg(h,n) for h,n in zip(so.hsg,so.muname)]
sid={"A":1,"B":2,"C":3,"D":4}
sarr=rasterize(((g,sid[x]) for g,x in zip(so.geometry,so.g)),out_shape=(H,W),transform=tr,fill=3,dtype="int32")
with rasterio.open(P+"Soils/Hydrologic Soil Groups.tif","w",**prof) as o: o.write(sarr,1)
SO=[(0,"NoData"),(1,"A"),(2,"B"),(3,"C"),(4,"D")]
lchdf(P+"Soils/Hydrologic Soil Groups.hdf","Soils",SO)
u,cnt=np.unique(sarr,return_counts=True); print("soils",dict(zip(u,np.round(cnt/cnt.sum()*100,1))))
# --- infiltration (SCS CN) table, TR-55 values
CN={"NoData":(68,79,86,89),"Building":(98,)*4,"Road":(98,)*4,"Pavement-Other":(98,)*4,"Residential Pervious":(39,61,74,80),
 "Commercial-Industrial Pervious":(39,61,74,80),"Transportation-Utility Pervious":(39,61,74,80),"Community-Recreation Pervious":(39,61,74,80),
 "Agriculture":(65,75,82,86),"Wooded":(30,55,70,77),"Vacant-Meadow":(30,58,71,78),"Mining-Quarry":(77,86,91,94),"Water":(98,)*4,"Parking (LU)":(98,)*4}
rows=[]
for _,n,_,_ in LC:
    c=CN[n]; ia=0.2; fmin={"A":0.30,"B":0.15,"C":0.05,"D":0.02}
    if n=="NoData": rows.append(("NoData",float(c[2]),ia,0.05))
    else: rows.append((f"{n} : NoData",float(c[2]),ia,0.05))
    for k,s in enumerate("ABCD"):
        rows.append((f"{n} : {s}",float(c[k]),ia,0.0 if c[k]>=98 else fmin[s]))
nv=max(len(r[0]) for r in rows)+1
with h5py.File(P+"Soils/Infiltration.hdf","w") as f:
    f.attrs["GUID"]=np.bytes_(str(uuid.uuid4())); f.attrs["LC Type"]=np.bytes_("InfiltrationSCSCurveNumber"); f.attrs["Version"]=np.bytes_("2.0")
    f.attrs["Virtual Dependencies"]=np.array([b"..\\Land Classification\\LandCover.hdf",b".\\Hydrologic Soil Groups.hdf"])
    f.attrs["Virtual Dependency Types"]=np.array([b"LandCover",b"Soils"])
    lcn=[n for _,n,_,_ in LC]; sn=[n for _,n in SO]; m=max(len(lcn),len(sn))
    dc=np.array([(lcn[i] if i<len(lcn) else "", sn[i] if i<len(sn) else "") for i in range(m)],dtype=[("LandCover",f"S{nl}"),("Hydrologic Soil Groups","S7")])
    f.create_dataset("Dependency Classifications",data=dc)
    f.create_dataset("Properties",data=np.array([("SCS Initial Loss Reset Time",24.0)],dtype=[("Name","S27"),("Value","<f4")]))
    f.create_dataset("Variables",data=np.array(rows,dtype=[("Name",f"S{nv}"),("Curve Number","<f4"),("Abstraction Ratio","<f4"),("Minimum Infiltration Rate","<f4")]))
print(len(rows),"infiltration rows")
# composite CN check over watershed
from rasterio.features import geometry_mask
msk=~geometry_mask([ws],out_shape=(H,W),transform=tr)
lcid={i:n for i,n,_,_ in LC}; cnarr=np.zeros((H,W),np.float32)
for i,n,_,_ in LC:
    for k,s in enumerate("ABCD"):
        cnarr[(arr==i)&(sarr==k+1)]=CN[n][k]
cnw=cnarr[msk].mean(); print("area-weighted CN",round(float(cnw),1))
S=1000/cnw-10; Pp=2.88; Q=(Pp-0.2*S)**2/(Pp+0.8*S); print("lumped runoff in",round(Q,2))
