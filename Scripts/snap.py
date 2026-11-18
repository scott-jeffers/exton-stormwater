import sys, numpy as np, rasterio, geopandas as gpd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rasterio.windows import from_bounds
x,y,R,out=float(sys.argv[1]),float(sys.argv[2]),float(sys.argv[3]),sys.argv[4]
ds=rasterio.open("ValleyCk_DEM_1m_ft.tif")
w=from_bounds(x-R,y-R,x+R,y+R,ds.transform); a=ds.read(1,window=w).astype(float); a[a==-9999]=np.nan
dx,dy=np.gradient(a,3.28); hs=np.cos(np.arctan(np.hypot(dx,dy)))  
fig,ax=plt.subplots(figsize=(8,8)); ext=[x-R,x+R,y-R,y+R]
ax.imshow(a,extent=ext,cmap="terrain"); ax.imshow(hs,extent=ext,cmap="gray",alpha=0.5)
cs=ax.contour(np.flipud(a),levels=range(int(np.nanmin(a)),int(np.nanmax(a)),5),extent=ext,colors='k',linewidths=0.3,origin='lower')
from shapely.geometry import box
b=box(x-R,y-R,x+R,y+R)
st=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Rivers_and_Streams",bbox=b.bounds); st.plot(ax=ax,color='blue',lw=1)
rd=gpd.read_file("mpk/v103/ms4munidata.gdb",layer="Roads",bbox=b.bounds); rd.plot(ax=ax,color='red',lw=0.8)
try:
  c=gpd.read_file("culvert_candidates.gpkg",bbox=b.bounds); c.plot(ax=ax,color='magenta',lw=3)
except Exception: pass
fl=gpd.read_file("flowlines.gpkg",bbox=b.bounds); fl.plot(ax=ax,color='cyan',lw=0.8,ls='--')
ax.set_xlim(x-R,x+R); ax.set_ylim(y-R,y+R); ax.set_title(f"{x:.0f},{y:.0f}")
plt.savefig(out,dpi=90,bbox_inches='tight')
