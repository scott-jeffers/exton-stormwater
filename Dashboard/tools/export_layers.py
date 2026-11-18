import geopandas as gpd, pandas as pd, json, re, numpy as np
from shapely.geometry import mapping
G='/'.join(__import__('os').path.expanduser('~/mnt/Exton-Model/Model_Build/ValleyCreek_HECRAS/GIS').split('/'))
OUT=__import__('os').path.expanduser('~/mnt/Exton-Model/Dashboard/data/')
def gj(gdf, cols, tol=None, prec=6):
    g=gdf.copy()
    if tol: g['geometry']=g.geometry.simplify(tol)
    g=g.to_crs(4326)
    feats=[]
    for _,r in g.iterrows():
        geom=mapping(r.geometry)
        def rnd(c):
            if isinstance(c,(list,tuple)):
                if len(c) and isinstance(c[0],(int,float)): return [round(c[0],prec),round(c[1],prec)]
                return [rnd(x) for x in c]
            return c
        geom={'type':geom['type'],'coordinates':rnd(geom['coordinates'])}
        props={}
        for k in cols:
            v=r[k]
            if isinstance(v,(np.floating,float)): v=None if np.isnan(v) else round(float(v),2)
            elif isinstance(v,np.integer): v=int(v)
            props[k]=v
        feats.append({'type':'Feature','geometry':geom,'properties':props})
    return {'type':'FeatureCollection','features':feats}
L={}
ws=gpd.read_file(G+'/Watershed_ValleyCreek.shp'); L['watershed']=gj(ws,['sqmi'],tol=10)
st=gpd.read_file(G+'/Streams_ValleyCreek.shp'); L['streams']=gj(st,['NAME'],tol=5)
cu=gpd.read_file(G+'/Culverts_Inferred.shp'); ct=pd.read_csv(G+'/Culvert_Table.csv')
cu=cu.merge(ct[['cid','crest','relief']],on='cid',how='left',suffixes=('','_t'))
cu['kind']='Culvert'
br=gpd.read_file(G+'/Bridge_Openings.shp'); br['kind']='Bridge'
for d in (cu,br):
    if 'crest' not in d: d['crest']=np.nan
xs=pd.concat([cu,br],ignore_index=True)
xs['geometry']=xs.geometry.centroid
L['crossings']=gj(gpd.GeoDataFrame(xs,crs=cu.crs),['cid','kind','shape','rise','span','barrels','road','stream','crest','da_ac','src'])
p=gpd.read_file(G+'/RAS_Pipe_Conduits_v2.shp'); p['dia_in']=(p['Rise']*12).round()
L['pipes']=gj(p,['Name','dia_in','USElev','DSElev','Length','dia_src','qa'],tol=1)
n=gpd.read_file(G+'/RAS_Pipe_Nodes_v2.shp'); o=n[n.NodeType=='Outfall']
L['outfalls']=gj(o,['Name','Invert','Terrain'])
mu=gpd.read_file(__import__('os').path.expanduser('~/mnt/Exton-Model/Chester_County_Municipalities.geojson'))
mu=mu.to_crs(ws.crs); mu=mu[mu.intersects(ws.geometry.iloc[0].buffer(5000))]
name=[c for c in mu.columns if re.search('name',c,re.I)][0]
L['municipalities']=gj(mu,[name],tol=30); 
for f in L['municipalities']['features']: f['properties']={'name':f['properties'][name]}
# atlas14
t=open('atlas14.txt').read(); q=re.search(r"quantiles = (\[\[.*?\]\])",t,re.S).group(1)
q=json.loads(q.replace("'",'"'))
durs=['5-min','10-min','15-min','30-min','60-min','2-hr','3-hr','6-hr','12-hr','24-hr','2-day','3-day','4-day','7-day','10-day','20-day','30-day','45-day','60-day']
L['atlas14']={'rp':[1,2,5,10,25,50,100,200,500,1000],'dur':durs[:len(q)],'depth':[[float(x) for x in r] for r in q],'lat':40.0176,'lon':-75.6346}
s=json.dumps(L,separators=(',',':'))
open(OUT+'model_layers.js','w').write('window.MODEL_LAYERS='+s+';\n')
print(len(s)/1e6,'MB', {k:len(v['features']) for k,v in L.items() if isinstance(v,dict) and 'features' in v})
