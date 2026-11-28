"""Move named BC lines 8 ft outside the 2D-area perimeter so HEC-RAS treats them as external.
Usage: bc_offset.py <proj.g01> <proj.g01.hdf> <BCname> [...]"""
import sys, numpy as np, h5py, shutil
from shapely.geometry import LineString, Polygon, Point
g01, hdf, names = sys.argv[1], sys.argv[2], sys.argv[3:]
shutil.copy2(g01, g01 + '.pre_bcoffset')
L=[l.rstrip('\r') for l in open(g01,encoding='latin-1').read().split('\n')]
per=Polygon(h5py.File(hdf,'r')['Geometry/2D Flow Areas/Polygon Points'][()])
def block(i,n):
    v=[];k=i+1
    while len(v)<2*n: v+=[float(L[k][a:a+16]) for a in range(0,len(L[k]),16) if L[k][a:a+16].strip()]; k+=1
    return np.array(v).reshape(-1,2),k
def pairs(c):
    vals=[v for xy in c for v in xy]; return ["".join(f"{v:16.6f}" for v in vals[q:q+4]) for q in range(0,len(vals),4)]
for nm in names:
    j=[x for x,l in enumerate(L) if l.startswith('BC Line Name=') and l.split('=')[1].strip()==nm][0]; k=j
    while not L[k].startswith('BC Line Arc='): k+=1
    P,e=block(k,int(L[k].split('=')[1])); ln=LineString(P)
    cands=[ln.offset_curve(d) for d in (8,-8)]
    o=max(cands,key=lambda c: np.mean([not per.contains(Point(q)) for q in c.coords]))
    seg=np.array(o.coords)
    if np.hypot(*(seg[0]-P[0]))>np.hypot(*(seg[-1]-P[0])): seg=seg[::-1]
    m=seg[len(seg)//2]
    L[k-3]=f"BC Line Start Position= {seg[0][0]:.6f} , {seg[0][1]:.6f} "; L[k-2]=f"BC Line Middle Position= {m[0]:.6f} , {m[1]:.6f} "; L[k-1]=f"BC Line End Position= {seg[-1][0]:.6f} , {seg[-1][1]:.6f} "
    L=L[:k]+[f"BC Line Arc= {len(seg)} "]+pairs(seg)+L[e:]
    print(nm,'moved outside, outside fraction',round(np.mean([not per.contains(Point(q)) for q in seg]),2))
open(g01,'w',encoding='latin-1',newline='\r\n').write('\n'.join(L))
