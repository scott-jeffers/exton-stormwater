import numpy as np, geopandas as gpd, rasterio, pyflwdir, pandas as pd
pd.set_option('display.width',250); pd.set_option('display.max_rows',300)
ds=rasterio.open("dem10ft.tif"); a=ds.read(1).astype(np.float32)
fill=pyflwdir.dem.fill_depressions(a,nodata=-9999,outlets="edge")[0]
fd=fill-a; np.save("filldepth10_raw.npy",fd)
g=gpd.read_file("culvert_candidates_raw.gpkg")
lu=gpd.read_file("lulc.gpkg"); mine=lu[lu.LU_TYPE=="11000"].buffer(50).union_all()
def fdmax(x,y,r=3):
    rr,cc=ds.index(x,y); return float(fd[max(rr-r,0):rr+r+1,max(cc-r,0):cc+r+1].max())
g['pond_us']=[fdmax(x,y) for x,y in zip(g.us_x,g.us_y)]
g['in_quarry']=g.geometry.intersects(mine)
keep=(~g.in_quarry)&(g.da_ac>=5)&(g.pond_us>=1.0)
print("kept",keep.sum(),"of",len(g)); print(g[~keep][['src','relief','length','da_ac','pond_us','in_quarry']].describe().round(1))
k=g[keep].sort_values('da_ac',ascending=False).copy()
# dedupe by centroid distance 60 ft
sel=[]
for i,r in k.iterrows():
    p=r.geometry.centroid
    if all(p.distance(k.loc[j].geometry.centroid)>60 for j in sel): sel.append(i)
k=k.loc[sel]
print("after dedupe",len(k)); print(pd.cut(k.length,[0,50,100,200,300,600,3000]).value_counts().sort_index())
print(k[['src','stream','relief','length','da_ac','pond_us','road']].sort_values('length',ascending=False).head(15).round(1).to_string())
k.to_file("culvert_candidates.gpkg")
