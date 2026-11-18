# one-time: 10-ft grid, DEM, mesh cell index raster, roads & buildings sample points
import h5py, numpy as np, rasterio, geopandas as gpd, pandas as pd, os
from rasterio.features import rasterize
from rasterio.enums import Resampling
from shapely.geometry import Polygon
P=os.path.expanduser('~/mnt/Exton-Model/Model_Build/ValleyCreek_HECRAS/')
f=h5py.File(P+'ValleyCreek.g01.hdf','r'); A='Geometry/2D Flow Areas/ValleyCreek/'
fpi=f[A+'Cells FacePoint Indexes'][:]; fpc=f[A+'FacePoints Coordinate'][:]
per=f[A+'Perimeter'][:]
x0,y0=per.min(0)-50; x1,y1=per.max(0)+50; R=10.0
W=int((x1-x0)/R); H=int((y1-y0)/R)
tr=rasterio.transform.from_origin(x0,y1,R,R)
shapes=[]
for i,row in enumerate(fpi):
    idx=row[row>=0]
    if len(idx)<3: continue
    shapes.append((Polygon(fpc[idx]).buffer(0),i))
cell=rasterize(shapes,out_shape=(H,W),transform=tr,fill=-1,dtype='int32')
dem=rasterio.open(P+'Terrain/ValleyCk_DEM_1m_ft_hydro_v2.tif')
from rasterio.warp import reproject
d=np.full((H,W),np.nan,'float32')
reproject(rasterio.band(dem,1),d,dst_transform=tr,dst_crs=dem.crs,resampling=Resampling.average,dst_nodata=np.nan)
np.savez_compressed('static.npz',cell=cell,dem=d,x0=x0,y1=y1,R=R)
print(W,H,(cell>=0).mean())
# roads -> 40ft sample points
ws=gpd.read_file(P+'GIS/Watershed_ValleyCreek.shp')
rd=gpd.read_file(os.path.expanduser('~/work/mpk/v103/ms4munidata.gdb'),layer='Roads').to_crs(ws.crs)
rd=rd[rd.intersects(ws.geometry.iloc[0])].copy()
print(rd.columns.tolist()); 
pass
pass
pass
