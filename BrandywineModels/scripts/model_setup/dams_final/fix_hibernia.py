"""Trim the NE end of the Hibernia dam connection (it reached the West Branch) to station s0 along segment 1."""
import sys, math, shutil, os
g=sys.argv[1]; s0=float(sys.argv[2]) if len(sys.argv)>2 else 90.5
raw=open(g,encoding='latin-1',newline='').read(); eol='\r\n' if '\r\n' in raw else '\n'; L=raw.split(eol)
i=[k for k,l in enumerate(L) if l.startswith('Connection=HiberniaDam')][0]
# line
k=[x for x in range(i,i+10) if L[x].startswith('Connection Line=')][0]; n=int(L[k].split('=')[1])
nums=[float(L[r][c:c+16]) for r in range(k+1,k+1+math.ceil(n*2/4)) for c in range(0,len(L[r].rstrip()),16) if L[r][c:c+16].strip()]
P=[(nums[2*a],nums[2*a+1]) for a in range(n)]
(x0,y0),(x1,y1)=P[0],P[1]; d=math.hypot(x1-x0,y1-y0); ux,uy=(x1-x0)/d,(y1-y0)/d
P[0]=(round(x0+ux*s0,2),round(y0+uy*s0,2))
flat=[v for p in P for v in p]; rows=[''.join(f'{v:16}' for v in flat[r:r+4]) for r in range(0,len(flat),4)]
L[k+1:k+1+math.ceil(n*2/4)]=rows
newlen=sum(math.hypot(P[a+1][0]-P[a][0],P[a+1][1]-P[a][1]) for a in range(n-1))
# weir
w=[x for x in range(i,i+60) if L[x].startswith('Conn Weir SE=')][0]; m=int(L[w].split('=')[1]); nr=math.ceil(m*2/10)
v=[float(L[r][c:c+8]) for r in range(w+1,w+1+nr) for c in range(0,len(L[r].rstrip()),8) if L[r][c:c+8].strip()]
S=list(zip(v[0::2],v[1::2]))
import bisect
for a in range(len(S)-1):
    if S[a][0]<=s0<=S[a+1][0]:
        z=S[a][1]+(S[a+1][1]-S[a][1])*(s0-S[a][0])/(S[a+1][0]-S[a][0]); break
S2=[(0.0,round(z,2))]+[(round(s-s0,2),e) for s,e in S if s>s0]
sc=newlen/S2[-1][0]; S2=[(round(s*sc,2),e) for s,e in S2]
fl=[q for p in S2 for q in p]
def f8(x):
    s=f'{x:8.2f}'.rstrip('0').rstrip('.') ; return f'{s:>8}'
rows=[''.join(f8(q) for q in fl[r:r+10]) for r in range(0,len(fl),10)]
L[w:w+1+nr]=[f'Conn Weir SE= {len(S2)} ']+rows
# culvert station line (line after Connection Culv=)
c=[x for x in range(w,w+80) if L[x].startswith('Connection Culv=')][0]
st=[float(t) for t in L[c+1].split()]
L[c+1]=''.join(f8(round((s-s0)*sc,1)) for s in st)
os.makedirs(os.path.join(os.path.dirname(g) or '.','Backup','pre_hibernia_fix'),exist_ok=True)
shutil.copy2(g,os.path.join(os.path.dirname(g) or '.','Backup','pre_hibernia_fix',os.path.basename(g)))
open(g,'w',encoding='latin-1',newline='').write(eol.join(L))
print('new first point',P[0],'line len',round(newlen,1),'weir end',S2[-1][0],'pts',len(S2),'culv sta',L[c+1])
