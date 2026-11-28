"""build_zip.py <base zip> <out zip> <ProjName> <plans comma> file1=arcname1 ...  : copy base zip (g01/terrain/etc.), drop old plan files, add given files, write trimmed prj."""
import sys, zipfile, re
base,out,nm,plans=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4].split(',')
adds=dict(a.split('=',1)[::-1] for a in sys.argv[5:])   # arcname -> path
src=zipfile.ZipFile(base); o=zipfile.ZipFile(out,'w')
for i in src.infolist():
    f=i.filename
    if re.search(r'\.(p|u)\d\d(\.hdf)?$',f) or 'Precipitation/' in f or f in adds: continue
    data=src.read(f)
    if f==f'{nm}/{nm}.prj':
        L=[l for l in data.decode('latin-1').split('\n') if not l.startswith(('Plan File=','Unsteady File='))]
        k=[a for a,l in enumerate(L) if l.startswith('Geom File=')][0]
        L[k+1:k+1]=[f'Unsteady File=u{p[1:]}\r' for p in plans]+[f'Plan File={p}\r' for p in plans]
        L=[(f'Current Plan={plans[0]}\r' if l.startswith('Current Plan=') else l) for l in L]
        data='\n'.join(L).encode('latin-1')
    o.writestr(i,data)
for a,p in adds.items(): o.write(p,a)
o.close(); print(out, [n for n in zipfile.ZipFile(out).namelist() if not n.endswith('.tif')])
