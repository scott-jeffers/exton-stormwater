"""Export a HEC-RAS plan's max results as a dashboard flood scenario.
usage: python3 export_scenario.py PLAN.pNN.hdf SCENARIO_ID "Display name" [--meta '{json}'] [--out DIR]"""
import sys, os, json, io, base64, argparse, h5py, numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.warp import reproject, calculate_default_transform, transform_bounds
from rasterio.enums import Resampling
from rasterio.features import rasterize
from PIL import Image
from shapely.geometry import mapping, Point, LineString
ap=argparse.ArgumentParser(); ap.add_argument('hdf'); ap.add_argument('sid'); ap.add_argument('name')
ap.add_argument('--meta',default='{}'); ap.add_argument('--out',default=os.path.expanduser('~/mnt/Exton-Model/Dashboard/data/scenarios'))
a=ap.parse_args(); here=os.path.dirname(os.path.abspath(__file__))
P=os.path.expanduser('~/mnt/Exton-Model/Model_Build/ValleyCreek_HECRAS/')
S=np.load(os.path.join(here,'static.npz')); cell=S['cell']; dem=S['dem']; x0=float(S['x0']); y1=float(S['y1']); R=float(S['R'])
H,W=cell.shape; tr=rasterio.transform.from_origin(x0,y1,R,R); CRS='EPSG:2272'
f=h5py.File(a.hdf,'r')
B='Results/Unsteady/Output/Output Blocks/Base Output/Summary Output/2D Flow Areas/ValleyCreek/'
wse=f[B+'Maximum Water Surface'][0]; cmin=f['Geometry/2D Flow Areas/ValleyCreek/Cells Minimum Elevation'][:] if 'Geometry/2D Flow Areas/ValleyCreek/Cells Minimum Elevation' in f else None
msgs=f['Results/Summary/Compute Messages (text)'][()]; msgs=(msgs[0] if not isinstance(msgs,bytes) else msgs).decode(errors='ignore')
complete = ('Finished Unsteady Flow Simulation' in msgs) or ('Complete Process' in msgs and 'killed' not in msgs and 'unstable' not in msgs.lower())
W_=np.where(cell>=0, wse[np.clip(cell,0,None)], np.nan)
cm=f['Geometry/2D Flow Areas/ValleyCreek/Cells Minimum Elevation'][:]
wet=np.where(cell>=0,(wse-cm)[np.clip(cell,0,None)]>0.1,False)
depth=W_-dem; depth[~np.isfinite(depth)|~wet]=np.nan; depth[depth<0.1]=np.nan
# ---- display rasters in web mercator
dt,dw,dh=calculate_default_transform(CRS,'EPSG:3857',W,H,x0,y1-H*R,x0+W*R,y1)
d3=np.full((dh,dw),np.nan,'float32')
reproject(depth.astype('float32'),d3,src_transform=tr,src_crs=CRS,dst_transform=dt,dst_crs='EPSG:3857',resampling=Resampling.nearest,src_nodata=np.nan,dst_nodata=np.nan)
west,south,east,north=rasterio.transform.array_bounds(dh,dw,dt)
west,south,east,north=transform_bounds('EPSG:3857','EPSG:4326',west,south,east,north)
# color ramp (ft): matches legend in app
bins=[0.25,0.5,1,2,3,5,1e9]
cols=[(173,216,240,150),(116,180,230,175),(49,130,206,195),(20,90,180,210),(8,48,140,225),(60,10,110,235)]
rgba=np.zeros((dh,dw,4),'uint8')
for i,c in enumerate(cols):
    m=(d3>=bins[i])&(d3<bins[i+1]); rgba[m]=c
def uri(img):
    bio=io.BytesIO(); img.save(bio,'PNG',optimize=True); return 'data:image/png;base64,'+base64.b64encode(bio.getvalue()).decode()
val=np.where(np.isfinite(d3),np.clip(np.round(d3*10),0,254),255).astype('uint8')
vis=uri(Image.fromarray(rgba,'RGBA')); vimg=uri(Image.fromarray(val,'L'))
def depth_at(x,y):
    c=int((x-x0)/R); r=int((y1-y)/R)
    if 0<=r<H and 0<=c<W: return depth[r,c]
    return np.nan
to4326=lambda g: gpd.GeoSeries([g],crs=CRS).to_crs(4326).iloc[0]
def rnd(c): return [round(c[0],6),round(c[1],6)]
# ---- roads
roads=gpd.read_file(os.path.join(here,'roads.gpkg'))
HIDEM=rasterio.open(P+'Terrain/ValleyCk_DEM_1m_ft_original.tif')
def road_depth(pts):
    out=[]
    zs=[v[0] for v in HIDEM.sample([(p.x,p.y) for p in pts])]
    for p,z in zip(pts,zs):
        c=int((p.x-x0)/R); r=int((y1-p.y)/R)
        if not (0<=r<H and 0<=c<W) or cell[r,c]<0: out.append(np.nan); continue
        k=cell[r,c]
        if (wse[k]-cm[k])<=0.1 or z<-1000: out.append(np.nan); continue
        out.append(wse[k]-z)
    return np.array(out)
streams=gpd.read_file(P+'GIS/Streams_ValleyCreek.shp').geometry.union_all().buffer(40).union(gpd.read_file(P+'GIS/Culvert_Barrel_Paths.shp').geometry.union_all().buffer(30))
out_roads=[]
for _,r in roads.iterrows():
    g=r.geometry; g=g.geoms[0] if g.geom_type.startswith('Multi') else g
    g=LineString([c[:2] for c in g.coords]); L=g.length
    if L<1: continue
    n=max(2,int(L/25)+1); pts=[g.interpolate(t,normalized=True) for t in np.linspace(0,1,n)]
    ds=road_depth(pts); ds[[streams.contains(p) for p in pts]]=np.nan
    wet=np.nan_to_num(ds)>=0.5
    if wet.sum()==0: continue
    # flooded sub-runs
    i=0
    while i<n:
        if wet[i]:
            j=i
            while j+1<n and wet[j+1]: j+=1
            seg=LineString([pts[max(i-1,0)],*pts[i:j+1],pts[min(j+1,n-1)]]) if j>i or True else None
            gg=to4326(seg)
            out_roads.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[rnd(c) for c in gg.coords]},
              'properties':{'name':(r.RD_NAME_FULL or r.RD_NAME or 'Unnamed road'),'max_ft':round(float(np.nanmax(ds[i:j+1])),2),
              'len_ft':round((j-i+1)*L/(n-1)),'evac':isinstance(r.EVAC_ROUTE_TYPE,str) and r.EVAC_ROUTE_TYPE.strip() not in ('','None'), 'major':(r.RD_CLASS in ('Highway','Primary','Secondary')) or (isinstance(r.HWY_FUNCTIONAL_CLASS,str) and any(k in r.HWY_FUNCTIONAL_CLASS for k in ('Arterial','Expressway','Collector'))), 'fclass':r.HWY_FUNCTIONAL_CLASS if isinstance(r.HWY_FUNCTIONAL_CLASS,str) else '',
              'owner':r.RD_OWNER, 'cls':r.RD_CLASS}})
            i=j+1
        else: i+=1
# ---- crossings (culverts/bridges): max WSE within 40 ft vs road crest
cu=gpd.read_file(P+'GIS/Culverts_Inferred.shp'); ct=pd.read_csv(P+'GIS/Culvert_Table.csv')
br=gpd.read_file(P+'GIS/Bridge_Openings.shp')
xs=pd.concat([cu.assign(kind='Culvert'),br.assign(kind='Bridge')],ignore_index=True)
xs=xs.merge(ct[['cid','crest']].rename(columns={'crest':'crest_t'}),on='cid',how='left')
out_x=[]
for _,r in xs.iterrows():
    c=r.geometry.centroid; cc=int((c.x-x0)/R); rr=int((y1-c.y)/R); k=4
    win=cell[max(rr-k,0):rr+k+1,max(cc-k,0):cc+k+1]; win=win[win>=0]
    if len(win)==0: continue
    crest=r['crest'] if pd.notna(r.get('crest')) else r.get('crest_t')
    if r.kind=='Bridge':
        buf=c.buffer(150); near=roads[roads.intersects(buf)]
        pts=[]
        for g in near.geometry:
            g=g.intersection(buf)
            for gg in (getattr(g,'geoms',None) or [g]):
                if gg.length<1: continue
                pts+=[gg.interpolate(t) for t in np.arange(0,gg.length,10)]
        span=max(float(r['span']) if pd.notna(r.get('span')) else 40.0, 40.0)
        pts=[p for p in pts if not streams.contains(p) and p.distance(c)>span/2+25]
        if pts:
            zz=np.array([v[0] for v in HIDEM.sample([(p.x,p.y) for p in pts])]); zz=zz[zz>-1000]
            if zz.size: crest=float(zz.min())
        else: crest=np.nan
    if pd.isna(crest): continue
    if pd.isna(crest): continue
    win=np.unique(win)
    # only cells low enough to be the road/channel area (not hillside sheet flow) and actually wet
    ok=win[(cm[win]<=float(crest)+0.5)&((wse[win]-cm[win])>0.3)]
    w=float(np.max(wse[ok])) if len(ok) else float(np.min(cm[win]))
    ot=w-float(crest); g=to4326(c)
    out_x.append({'type':'Feature','geometry':{'type':'Point','coordinates':rnd(g.coords[0])},
      'properties':{'id':('B'+r.cid[1:]) if r.kind=='Bridge' else r.cid,'kind':r.kind,'road':r.road if isinstance(r.road,str) else '','stream':r.stream if isinstance(r.stream,str) else '',
      'wse':round(w,2),'crest':round(float(crest),2),'overtop_ft':round(ot,2)}})
# ---- buildings
bl=gpd.read_file(os.path.join(here,'buildings.gpkg')); bl=bl[bl.intersects(gpd.GeoSeries([streams.envelope],crs=CRS).iloc[0])] if False else bl
ids=rasterize(((g.buffer(5),i+1) for i,g in enumerate(bl.geometry)),out_shape=(H,W),transform=tr,fill=0,all_touched=True,dtype='int32')
dm=np.nan_to_num(depth,nan=0.0); mx=np.zeros(len(bl)+1,'float32'); np.maximum.at(mx,ids.ravel(),dm.ravel())
out_b=[]
cent=bl.geometry.centroid.to_crs(4326)
for i in np.where(mx[1:]>=0.5)[0]:
    out_b.append({'type':'Feature','geometry':{'type':'Point','coordinates':rnd((cent.iloc[i].x,cent.iloc[i].y))},
      'properties':{'upi':bl.iloc[i].UPI,'max_ft':round(float(mx[i+1]),2)}})

# ---- vector flood extent (for SARTopo/CalTopo export)
from rasterio.features import shapes as rshapes
from shapely.geometry import shape as sshape
cls=np.zeros(depth.shape,'uint8'); dd=np.nan_to_num(depth,nan=0)
cls[dd>=1]=1; cls[dd>=3]=2
ext=[]
for geom,v in rshapes(cls,mask=cls>0,transform=tr):
    g=sshape(geom)
    if g.area<2000: continue
    g=g.simplify(8)
    if g.is_empty: continue
    g4=gpd.GeoSeries([g],crs=CRS).to_crs(4326).iloc[0]
    m=mapping(g4)
    def r6(c):
        return [round(c[0],6),round(c[1],6)] if isinstance(c[0],(int,float)) else [r6(x) for x in c]
    ext.append({'type':'Feature','geometry':{'type':m['type'],'coordinates':r6(m['coordinates'])},'properties':{'depth_class':'1-3 ft' if v==1 else '3+ ft'}})

area=np.nansum(depth>=0.5)*R*R/43560
stats={'flooded_acres_0p5ft':round(float(area),1),'max_depth_ft':round(float(np.nanmax(depth)) if np.isfinite(depth).any() else 0,1),
 'roads_flooded':len(out_roads),'road_names':sorted({x['properties']['name'] for x in out_roads}),
 'crossings_overtopped':sum(1 for x in out_x if x['properties']['overtop_ft']>0),'buildings_wet':len(out_b),'run_complete':bool(complete)}
meta=json.loads(a.meta); meta.update({'id':a.sid,'name':a.name,'source_hdf':os.path.basename(a.hdf)})
obj={'meta':meta,'stats':stats,'bounds':[[south,west],[north,east]],'depth_png':vis,'value_png':vimg,'value_scale':0.1,
 'roads':{'type':'FeatureCollection','features':out_roads},'crossings':{'type':'FeatureCollection','features':out_x},
 'buildings':{'type':'FeatureCollection','features':out_b},'extent':{'type':'FeatureCollection','features':ext}}
os.makedirs(a.out,exist_ok=True)
s='(window.SCENARIO_DATA=window.SCENARIO_DATA||{})['+json.dumps(a.sid)+']='+json.dumps(obj,separators=(',',':'))+';\n'
open(os.path.join(a.out,a.sid+'.js'),'w').write(s)
print(json.dumps(stats)[:600], len(s)/1e6,'MB')
