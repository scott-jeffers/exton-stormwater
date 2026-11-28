import sys, re, shutil, os
src, name, dst = sys.argv[1:4]   # src folder with prj/u18/p18; project name; out folder
os.makedirs(dst, exist_ok=True)
u=open(f'{src}/{name}.u18',encoding='latin-1').read().split('\n')
# drop the Precipitation Hydrograph boundary block (Boundary Location line .. next Boundary Location / Met lines)
out=[];i=0;blocks=[]
cur=[]
head=[];body=[]
# split into chunks starting at 'Boundary Location='
chunks=[[]]
for l in u:
    if l.startswith('Boundary Location=') or l.startswith('Met Point Raster') or l.startswith('Precipitation Mode='):
        chunks.append([])
    chunks[-1].append(l)
keep=[]
for c in chunks:
    if any(x.startswith('Precipitation Hydrograph=') for x in c): continue
    keep+=c
txt='\n'.join(keep)
txt=re.sub(r'^Flow Title=.*$','Flow Title=Ida 2021 MRMS radar (gridded)',txt,flags=re.M)
open(f'{dst}/{name}.u19','w',newline='\r\n' if False else '\n').write(txt)
p=open(f'{src}/{name}.p18',encoding='latin-1').read()
p=re.sub(r'^Plan Title=.*$','Plan Title=Ida 2021 MRMS radar rain',p,flags=re.M)
p=re.sub(r'^Short Identifier=.*$','Short Identifier=IdaMRMS',p,flags=re.M)
p=re.sub(r'^Simulation Date=.*$','Simulation Date=01JAN2026,0000,02JAN2026,1200',p,flags=re.M)
p=re.sub(r'^Flow File=.*$','Flow File=u19',p,flags=re.M)
open(f'{dst}/{name}.p19','w').write(p)
pr=open(f'{src}/{name}.prj',encoding='latin-1').read()
if 'Plan File=p19' not in pr:
    pr=pr.replace('Plan File=p18','Plan File=p18\nPlan File=p19',1).replace('Unsteady File=u18','Unsteady File=u18\nUnsteady File=u19',1)
open(f'{dst}/{name}.prj','w').write(pr)
print('ok', sum(1 for c in chunks if any(x.startswith('Precipitation Hydrograph=') for x in c)),'precip blocks removed')
