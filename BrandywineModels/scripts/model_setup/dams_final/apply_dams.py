"""Add flood-control dams to the Brandywine 2D models (run from EBBrandywine-Model root).
1) restores the dam embankments that were cut through as culverts (terrain tiles),
2) adds an SA/2D connection per dam (weir = crest profile from lidar, culvert = principal spillway),
3) aligns mesh points to each connection line (paired points, 25 ft)."""
import json, os, shutil, sys, glob, numpy as np, rasterio
from rasterio.warp import reproject, Resampling
from shapely.geometry import LineString
import shapely
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.getcwd()
D=json.load(open(f'{HERE}/dams.json'))
PROJ={'M03':('Upper_EB_Marsh_HECRAS','UpperEBMarsh'),'M02':('Downingtown_HECRAS','Downingtown'),'M04':('WBCoatesville_HECRAS','WBCoatesville')}
H=25.0
def pairs(coords,per_line=4):
    vals=[v for xy in coords for v in xy]; out=[]
    for i in range(0,len(vals),per_line): out.append("".join(f"{v:>16.6f}"[-16:] if len(f'{v:.6f}')<=16 else f"{v:16.4f}" for v in vals[i:i+per_line]))
    return out
def fmt8(v):
    s=f"{v:8.2f}"
    if len(s)>8: s=f"{v:8.1f}"
    if len(s)>8: s=f"{v:8.0f}"
    return s
ONLY=sys.argv[1:] or list(PROJ)
for m,(folder,name) in [(k,v) for k,v in PROJ.items() if k in ONLY]:
    P=f'{ROOT}/{folder}'; bk=f'{P}/Backup/pre_dams'; os.makedirs(bk,exist_ok=True)
    g01=f'{P}/{name}.g01'
    if not os.path.exists(f'{bk}/{name}.g01'): shutil.copy2(g01,bk)
    # ---- terrain
    tifs=[t for t in glob.glob(f'{P}/Terrain/*.tif')]
    for pt in [p for p in D['patches'] if p['model']==m]:
        src=rasterio.open(f"{HERE}/{pt['file']}"); A=src.read(1)
        for t in tifs:
            with rasterio.open(t) as ds:
                b=ds.bounds; sb=src.bounds
                if sb.left>b.right or sb.right<b.left or sb.bottom>b.top or sb.top<b.bottom: continue
            if not os.path.exists(f'{bk}/{os.path.basename(t)}.patched'): open(f'{bk}/{os.path.basename(t)}.patched','w').write('patched in place by apply_dams.py; originals are rebuildable from Data/Terrain sources\n')
            with rasterio.open(t,'r+') as ds:
                w=rasterio.windows.from_bounds(*sb,ds.transform).round_offsets().round_lengths()
                w=w.intersection(rasterio.windows.Window(0,0,ds.width,ds.height))
                cur=ds.read(1,window=w); new=np.full(cur.shape,-9999,'float32')
                reproject(A,new,src_transform=src.transform,src_crs=src.crs,dst_transform=ds.window_transform(w),dst_crs=ds.crs,src_nodata=-9999,dst_nodata=-9999,resampling=Resampling.nearest)
                nd=ds.nodata if ds.nodata is not None else -9999
                ok=(new>-9000)&(cur!=nd)&(new>cur)
                cur[ok]=new[ok].astype(cur.dtype); ds.write(cur,1,window=w)
                print(m,os.path.basename(t),pt['file'],'cells raised',int(ok.sum()),'max',round(float((new-cur.astype('float32'))[ok].max()) if ok.any() else 0,1))
    # ---- geometry text
    L=open(g01,encoding='latin-1').read().split('\n'); L=[l.rstrip('\r') for l in L]
    if any(l.startswith('Connection=') and 'Dam' in l for l in L): print(m,'already has dam connections - skipped g01'); continue
    SA=[l for l in L if l.startswith('Storage Area=')][0].split('=')[1].split(',')[0].strip()
    i0=[i for i,l in enumerate(L) if l.startswith('Storage Area 2D Points=')][0]
    i1=[i for i,l in enumerate(L) if l.startswith('Storage Area 2D PointsPerimeterTime')][0]
    vals=np.array([float(l[j:j+16]) for l in L[i0+1:i1] for j in range(0,len(l),16) if l[j:j+16].strip()],float); pts=vals.reshape(-1,2)
    blocks=[]; n0=len(pts)
    for k,d in D['dams'].items():
        if d['model']!=m: continue
        ln=LineString(d['line']); uo,do=d['up_off'],d['dn_off']; SP=40.0
        # big cells on each side so their lowest point is the dam toe / streambed (culvert ends sit in those cells)
        ls_=ln.length; dl=[]
        for s in np.arange(0,ls_+0.01,2.0):
            dl.append(np.array(ln.interpolate(s).coords[0]))
        dl=np.array(dl)
        P_=shapely.points(pts); dist=shapely.distance(P_,ln); near=dist<1.25*max(uo,do)+5
        if near.any():
            sn=shapely.line_locate_point(ln,P_[near]); a_=np.array([ln.interpolate(max(x-1,0)).coords[0] for x in sn]); b_=np.array([ln.interpolate(min(x+1,ls_)).coords[0] for x in sn])
            uu=b_-a_; lf=np.c_[-uu[:,1],uu[:,0]]; side=np.sign(((pts[near]-(a_+b_)/2)*lf).sum(1))   # +1 = downstream (left)
            lim=np.where(side>0,1.25*do,1.25*uo); drop=np.zeros(len(pts),bool); drop[np.where(near)[0]]=dist[near]<lim
            pts=pts[~drop]
        new=[]
        for s in np.arange(SP/2,ls_,SP):
            p=np.array(ln.interpolate(s).coords[0]); q=np.array(ln.interpolate(min(s+1,ls_)).coords[0]); r_=np.array(ln.interpolate(max(s-1,0)).coords[0])
            u=(q-r_)/np.linalg.norm(q-r_); left=np.array([-u[1],u[0]])   # downstream is on the left
            new+= [p+left*do,p-left*uo]
        new=np.array(new)
        # keep only new points whose nearest line point is the foot of their perpendicular (avoid crossing at bends)
        ok=np.abs(shapely.distance(shapely.points(new),ln)-np.where(np.arange(len(new))%2==0,do,uo))<0.25*SP
        pts=np.vstack([pts,new[ok]])
        nm=(k+'Dam')[:16]; mid=ln.interpolate(0.5,normalized=True)
        B=[f"Connection={nm:<16},{mid.x:.4f},{mid.y:.4f}",f"Connection Desc={d['desc']}",f"Connection Line={len(ln.coords)}"]
        B+=pairs(list(ln.coords),4)
        B+=["Connection Last Edited Time=Nov/26/2026 12:00:00","Conn Near Repeats=1","Conn Protection Radius=-1",
            f"Connection Up SA={SA}",f"Connection Dn SA={SA}","Conn Routing Type= 1 ","Conn Use RC Family=False",
            "Conn OverFlow Method 2D=True","Conn Weir WD=20","Conn Weir Coef=2.6","Conn Weir WSCriteria=-1 ","Conn Weir Is Ogee= 0 ",
            "Conn Simple Spill Pos Coef=0.05","Conn Simple Spill Neg Coef=0.05",f"Conn Weir SE= {len(d['weir'])} "]
        W=np.array(d['weir']); W[:,0]*=ln.length/W[-1,0]
        v=[x for se in W.tolist() for x in se]
        for i in range(0,len(v),10): B.append("".join(fmt8(x) for x in v[i:i+10]))
        n=0.013
        if d['culv_shape']=='pipe': B.append(f"Connection Culv=1,{d['rise']:g},,{d['length']:.1f},{n},0.5,1,1,1,{d['us_inv']:.2f},{d['ds_inv']:.2f}, 1 ,{'Spillway':<12}, 0 ,,0")
        else: B.append(f"Connection Culv=2,{d['rise']:g},{d['span']:g},{d['length']:.1f},{n},0.5,1,8,1,{d['us_inv']:.2f},{d['ds_inv']:.2f}, 1 ,{'Spillway':<12}, 0 ,,0")
        B+=[fmt8(d['culv_sta'])+fmt8(d['culv_sta']),"Conn Culvert Barrel=1,Barrel #1,0",f"Conn Culv Bottom n={n}",
            f"Conn HTab HWMax={d['crest']+15:.1f}","","Conn Outlet Rating Curve= 0 ,False,,",""]
        blocks+=B
        print(m,k,'connection added; weir pts',len(d['weir']),'culvert',d['culv_shape'],d['rise'],d['span'],'us/ds',d['us_inv'],d['ds_inv'])
    L=L[:i0]+[f"Storage Area 2D Points= {len(pts)} "]+pairs([tuple(p) for p in pts],4)+L[i1:]
    j=[i for i,l in enumerate(L) if l.startswith('BC Line Name=')][0]
    L=L[:j]+blocks+L[j:]
    open(g01,'w',encoding='latin-1',newline='\r\n').write('\n'.join(L))
    print(m,'mesh points',n0,'->',len(pts))
