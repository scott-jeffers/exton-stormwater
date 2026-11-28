"""pack_release.py <src project folder> <out zip> <arc root> [budget s] : resumable zip of HEC-RAS model inputs for public release.
Re-run until it prints DONE. Keeps prj, g##(.hdf), rasmap, p##/u## (+u##.hdf), restart .rst, Terrain, Land Classification, Soils, Precipitation.
Drops results (p##.hdf, *.tmp.hdf, dss, b/bco/ic/x), Backup, GIS, Results_Archive."""
import sys, os, re, zipfile, time
src, out, root = sys.argv[1:4]; budget = float(sys.argv[4]) if len(sys.argv) > 4 else 140
t0 = time.time()
KEEP_DIRS = ('Terrain', 'Land Classification', 'Soils', 'Precipitation')
KEEP = re.compile(r'.*\.(prj|rasmap|g\d\d|g\d\d\.hdf|p\d\d|u\d\d|u\d\d\.hdf|p\d\d\..*\.rst)$', re.I)
files = []
def terrain_refs(d):
    try: b=open(os.path.join(d,'Terrain.hdf'),'rb').read()
    except OSError: return None
    return set(m.decode('latin-1').split('\\')[-1].split('/')[-1] for m in re.findall(rb'[\w .\\/-]+\.tif', b))
for dp, dn, fn in os.walk(src):
    rel = os.path.relpath(dp, src); top = rel.split(os.sep)[0]
    if rel != '.' and top not in KEEP_DIRS: dn[:] = []; continue
    for f in sorted(fn):
        if rel == '.' and not KEEP.match(f): continue
        if top == 'Terrain' and f.lower().endswith('.tif'):
            refs = terrain_refs(dp)
            if refs is not None and f not in refs: continue
        if f.endswith(('.tmp.hdf', '.backup')) or 'backup' in f.lower(): continue
        files.append((os.path.join(dp, f), (root + '/' + (rel.replace(os.sep, '/') + '/' if rel != '.' else '') + f)))
part = out + '.part'
have = set(zipfile.ZipFile(part).namelist()) if os.path.exists(part) else set()
with zipfile.ZipFile(part, 'a', allowZip64=True) as z:
    for p, a in files:
        if a in have: continue
        if time.time() - t0 > budget: print('PARTIAL', len(z.namelist()), '/', len(files)); sys.exit(0)
        comp = zipfile.ZIP_STORED if a.lower().endswith(('.tif', '.nc')) else zipfile.ZIP_DEFLATED
        z.write(p, a, compress_type=comp, compresslevel=1)
os.replace(part, out); print('DONE', out, len(files), 'files', round(os.path.getsize(out) / 1e6), 'MB')
