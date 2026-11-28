"""fill_u.py <u file> <BC name> <series.json key|file:path> : replace a Flow Hydrograph block (5-min) in a .u file.
Series = list of cfs at 5-min from plan start; padded/truncated to the plan window length n."""
import sys, json, math, numpy as np
def fill(ufile, bc, q, n):
    raw=open(ufile,encoding='latin-1',newline='').read(); eol='\r\n' if '\r\n' in raw else '\n'
    L=raw.split(eol); i=[k for k,l in enumerate(L) if l.startswith('Boundary Location=') and bc in l][0]
    j=i+1
    while not L[j].startswith('Flow Hydrograph='): j+=1
    old=int(L[j].split('=')[1]); nl=math.ceil(old/10)
    q=list(q[:n])+[q[-1]]*max(0,n-len(q))
    rows=[''.join(f'{v:8.1f}' if v<1e5 else f'{v:8.0f}' for v in q[r:r+10]) for r in range(0,n,10)]
    L[j:j+1+nl]=[f'Flow Hydrograph= {n} ']+rows
    open(ufile,'w',encoding='latin-1',newline='').write(eol.join(L))
def recess(q, n):
    q=list(q)
    while len(q)<n:
        r=min(1,(q[-1]/q[-13])**(1/12)) if q[-13]>0 else 1; q.append(q[-1]*r)
    return q[:n]
if __name__=='__main__':
    u,bc,src,n=sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4])
    q=json.load(open(src)); fill(u,bc,recess(q,n),n); print('filled',bc,n)
