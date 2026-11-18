import numpy as np, geopandas as gpd, rasterio, json, math, re, os
from shapely.geometry import LineString
P="proj/ValleyCreek/"; NAME="ValleyCreek"; SA=f"{NAME:<16}"
per=gpd.read_file("perimeter.gpkg").geometry.iloc[0]
bc=gpd.read_file("bcline.gpkg").geometry.iloc[0]
pts=np.load("mesh_points.npy")
cu=gpd.read_file(__import__("os").environ.get("CULV","culverts_model_in.gpkg"))
dem=rasterio.open(__import__("os").environ.get("DEMF","ValleyCk_DEM_1m_ft_hydro.tif")); A=dem.read(1); H,W=A.shape
def z(x,y):
    r,c=dem.index(x,y); v=A[r,c] if 0<=r<H and 0<=c<W else -9999
    return float(v) if v>-9000 else np.nan
f16=lambda v: f"{v:16.6f}"[:16] if abs(v)<1e9 else f"{v:16.6e}"
def pairs(coords,per_line):  # coords list of (x,y)
    vals=[v for xy in coords for v in xy]; out=[]
    for i in range(0,len(vals),per_line): out.append("".join(f"{v:>16.6f}"[-16:] if len(f'{v:.6f}')<=16 else f"{v:16.4f}" for v in vals[i:i+per_line]))
    return out
def fmt8(v):
    s=f"{v:8.2f}"
    if len(s)>8: s=f"{v:8.1f}"
    if len(s)>8: s=f"{v:8.0f}"
    return s
def dp(sta,el,tol=0.25):
    # Douglas-Peucker on station-elevation
    keep=np.zeros(len(sta),bool); keep[0]=keep[-1]=True
    stack=[(0,len(sta)-1)]
    while stack:
        i,j=stack.pop()
        if j<=i+1: continue
        x=sta[i+1:j]; y=el[i+1:j]
        yl=el[i]+(el[j]-el[i])*(x-sta[i])/(sta[j]-sta[i])
        k=np.argmax(abs(y-yl))
        if abs(y-yl)[k]>tol: kk=i+1+k; keep[kk]=True; stack+= [(i,kk),(kk,j)]
    return sta[keep],el[keep]
x0,y0,x1,y1=per.bounds
L=[]
L.append("Geom Title="+__import__("os").environ.get("GTITLE","Valley Creek 2D Rain-on-Grid w Culverts"))
L.append("Program Version=6.70")
L.append(f"Viewing Rectangle= {x0:.2f} , {x1:.2f} , {y1:.2f} , {y0:.2f} ")
L.append("")
c=per.centroid
L.append(f"Storage Area={SA},{c.x:.4f},{c.y:.4f}")
pc=list(per.exterior.coords)
L.append(f"Storage Area Surface Line= {len(pc)} ")
L+=pairs([(p[0],p[1]) for p in pc],2)
L+=["Storage Area Type= 1 ","Storage Area Area=","Storage Area Min Elev=","Storage Area Is2D=-1","Storage Area Point Generation Data=,,60,60"]
L.append(f"Storage Area 2D Points= {len(pts)} ")
L+=pairs([tuple(p) for p in pts],4)
L+=["Storage Area 2D PointsPerimeterTime=13Nov2026 12:00:00","Storage Area Mannings=0.06",
"2D Cell Volume Filter Tolerance=0.01","2D Cell Minimum Area Fraction=0.01","2D Face Profile Filter Tolerance=0.01",
"2D Face Area Elevation Profile Filter Tolerance=0.01","2D Face Area Elevation Conveyance Ratio=0.02","2D Face Min Length Ratio=0.05",
"2D Face Area Laminar Depth=0.2","2D Multiple Face Mann n=0","2D Composite LC=0",""]
recs=[]
for _,r in cu.iterrows():
    g=r.geometry; Lg=g.length
    sta=np.arange(0,Lg,5.0); sta=np.append(sta,Lg)
    el=np.array([z(*g.interpolate(s).coords[0]) for s in sta])
    el=np.where(np.isnan(el),np.nanmax(el),el)
    s2,e2=dp(sta,el)
    if len(s2)>150: s2,e2=dp(sta,el,0.5)
    mid=g.interpolate(0.5,normalized=True)
    L.append(f"Connection={r.cid:<16},{mid.x:.4f},{mid.y:.4f}")
    L.append(f"Connection Desc=Inferred from lidar: {r.stream or ''} at {r.road or 'unnamed crossing'}; DA={r.da_ac:.0f} ac; Q10est={r.q10_est:.0f} cfs")
    L.append(f"Connection Line={len(g.coords)}")
    L+=pairs(list(g.coords),4)
    L+=["Connection Last Edited Time=Nov/13/2026 12:00:00","Conn Near Repeats=1","Conn Protection Radius=-1",
        f"Connection Up SA={SA}",f"Connection Dn SA={SA}","Conn Routing Type= 1 ","Conn Use RC Family=False",
        "Conn OverFlow Method 2D=True",f"Conn Weir WD=40","Conn Weir Coef=2.6","Conn Weir Is Ogee= 0 ",
        "Conn Simple Spill Pos Coef=0.05","Conn Simple Spill Neg Coef=0.05"]
    L.append(f"Conn Weir SE= {len(s2)} ")
    vals=[v for se in zip(s2,e2) for v in se]
    for i in range(0,len(vals),10): L.append("".join(fmt8(v) for v in vals[i:i+10]))
    cs=r.conn_half_l
    w=(r.span if r['shape']==2 else r.rise)+2.0
    offs=[(k-(r.barrels-1)/2)*w for k in range(r.barrels)]
    n=0.013
    for k,o in enumerate(offs):
        stn=min(max(cs+o,1),Lg-1)
        if r['shape']==1: L.append(f"Connection Culv=1,{r.rise:g},,{r['length']:.1f},{n},0.5,1,1,1,{r.us_inv:.2f},{r.ds_inv:.2f}, 1 ,{('Barrel'+str(k+1)):<12}, 0 ,")
        else: L.append(f"Connection Culv=2,{r.rise:g},{r.span:g},{r['length']:.1f},{n},0.5,1,8,1,{r.us_inv:.2f},{r.ds_inv:.2f}, 1 ,{('Box'+str(k+1)):<12}, 0 ,")
        L.append(fmt8(stn)+fmt8(stn))
        L.append(f"Conn Culv Bottom n={n}")
    L.append(f"Conn HTab HWMax={r.crest+20:.1f}")
    L.append("Conn Outlet Rating Curve= 0 ,False,,")
    L.append("")
# BC line
bcc=list(bc.coords); m=bc.interpolate(0.5,normalized=True)
L+=[f"BC Line Name={'Outlet':<32}",f"BC Line Storage Area={SA}",
    f"BC Line Start Position= {bcc[0][0]} , {bcc[0][1]} ",f"BC Line Middle Position= {m.x} , {m.y} ",f"BC Line End Position= {bcc[-1][0]} , {bcc[-1][1]} ",
    f"BC Line Arc= {len(bcc)} "]
L+=pairs(bcc,4)
L+=["BC Line Text Position= 1.79769313486232E+308 , 1.79769313486232E+308 ",
"LCMann Time=Dec/30/1899 00:00:00","LCMann Region Time=Dec/30/1899 00:00:00","LCMann Table=0","Chan Stop Cuts=-1 ","","","",
"Use User Specified Reach Order=0","GIS Ratio Cuts To Invert=-1","GIS Limit At Bridges=0","Composite Channel Slope=5",""]
open(P+"ValleyCreek.g01","w",newline="\r\n").write("\n".join(L))
print("g01 lines",len(L))
# ---------- unsteady
st=json.load(open("storm.json")); inc=st["incremental_in"]+[0.0]*(216-72)
u=open("tpl.u01").read().splitlines()
out=[]; i=0
while i<len(u):
    s=u[i]
    if s.startswith("Flow Title="): out.append("Flow Title=5yr 6hr SCS Type II (Atlas14 2.88in)"); i+=1; continue
    if s.startswith("Boundary Location=") and "DS Normal" in s:
        out.append(f"Boundary Location={'':16},{'':16},{'':8},{'':8},{'':16},{SA},{'':16},{'Outlet':<32},{'':32}")
        out.append("Friction Slope=0.003,0"); i+=2; continue
    if s.startswith("Boundary Location=") and "area2" in s:
        out.append(f"Boundary Location={'':16},{'':16},{'':8},{'':8},{'':16},{SA},{'':16},{'':32},{'':32}")
        out.append("Interval=5MIN"); out.append(f"Precipitation Hydrograph= {len(inc)} ")
        for k in range(0,len(inc),10): out.append("".join(f"{v:8.4f}" for v in inc[k:k+10]))
        i+=1
        while not u[i].startswith("DSS Path="): i+=1
        continue
    out.append(s); i+=1
open(P+"ValleyCreek.u01","w",newline="\r\n").write("\n".join(out)+"\n")
# ---------- plan
p=open("tpl.p02").read().splitlines(); out=[]
d2=[]; inblock=False; firstblock=None
i=0
while i<len(p):
    s=p[i]
    if s.startswith("Plan Title="): s="Plan Title=5yr 6hr Type II Rain-on-Grid"
    elif s.startswith("Short Identifier="): s="Short Identifier=5yr6hrTypeII"
    elif s.startswith("Simulation Date="): s="Simulation Date=01JAN2026,0000,01JAN2026,1800"
    elif s.startswith("Geom File="): s="Geom File=g01"
    elif s.startswith("Flow File="): s="Flow File=u01"
    elif s.startswith("Computation Interval="): s="Computation Interval=10SEC"
    elif s.startswith("Output Interval="): s="Output Interval=5MIN"
    elif s.startswith("Mapping Interval="): s="Mapping Interval=10MIN"
    elif s.startswith("Computation Time Step Use Courant="): s="Computation Time Step Use Courant=        1"
    elif s.startswith("Computation Time Step Max Courant="): s="Computation Time Step Max Courant=2"
    elif s.startswith("Computation Time Step Min Courant="): s="Computation Time Step Min Courant=0.5"
    elif s.startswith("Computation Time Step Max Doubling="): s="Computation Time Step Max Doubling=3"
    elif s.startswith("Computation Time Step Max Halving="): s="Computation Time Step Max Halving=4"
    elif s.startswith("Run PostProcess="): s="Run PostProcess=-1 "
    elif s.startswith("UNET D2 Name="):
        if firstblock is None:
            firstblock=True; out.append(f"UNET D2 Name={SA}"); i+=1
            while i<len(p) and not p[i].startswith("UNET D2 Name="): 
                if not p[i].startswith("PS "): out.append(p[i])
                i+=1
            # skip second area block
            i+=1
            while i<len(p) and (p[i].startswith("UNET D2") or p[i].startswith("PS ")): i+=1
            continue
    if s.startswith("PS "): i+=1; continue
    out.append(s); i+=1
open(P+"ValleyCreek.p01","w",newline="\r\n").write("\n".join(out)+"\n")
# ---------- project
pj=open("tpl.prj").read().replace("Proj Title=DavisStormSystem","Proj Title=Valley Creek (Exton PA) 1D-2D").replace("Current Plan=p02","Current Plan=p01").replace("Geom File=g02","Geom File=g01").replace("Plan File=p02","Plan File=p01")
open(P+"ValleyCreek.prj","w",newline="\r\n").write(pj)
print(open(P+"ValleyCreek.p01").read().count("UNET D2 Name"))
