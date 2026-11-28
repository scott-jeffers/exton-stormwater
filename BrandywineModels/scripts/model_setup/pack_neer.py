"""Zip one HEC-RAS project for a NEER run (only what RAS needs), then split into 300 MB parts."""
import sys, os, zipfile, glob
fd, nm, plans = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
out = f'_to_delete/neer/{nm}.zip'; os.makedirs('_to_delete/neer', exist_ok=True)
files = [f'{nm}.prj', f'{nm}.g01', f'{nm}.g01.hdf', f'{nm}.rasmap'] + [f'{nm}.{p}' for p in plans] + [f'{nm}.u{p[1:]}' for p in plans]
files += [f'{nm}.u{p[1:]}.hdf' for p in plans if os.path.exists(f'{fd}/{nm}.u{p[1:]}.hdf')]  # u.hdf: gridded precip
files += [os.path.relpath(f, fd) for f in glob.glob(f'{fd}/Precipitation/**/*.nc', recursive=True)]
files += [os.path.relpath(f, fd) for f in glob.glob(f'{fd}/Terrain/Terrain*') + glob.glob(f'{fd}/Terrain/Projection.prj') + glob.glob(f'{fd}/Land Classification/*') + glob.glob(f'{fd}/Soils/*')]
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    for f in files:
        p = f'{fd}/{f}'
        if f.endswith('.prj') and f == f'{nm}.prj':
            keep = set([f'Plan File={q}' for q in plans] + [f'Unsteady File=u{q[1:]}' for q in plans])
            L = [l for l in open(p, encoding='latin-1').read().split('\n') if not (l.startswith(('Plan File=', 'Unsteady File=', 'Steady File=')) and l.strip() not in keep)]
            L = [f'Current Plan={plans[0]}' if l.startswith('Current Plan=') else l for l in L]
            z.writestr(f'{nm}/{f}', '\n'.join(L)); continue
        if os.path.exists(p): z.write(p, f'{nm}/'+f.replace(os.sep,'/'), compress_type=zipfile.ZIP_STORED if p.endswith('.tif') else zipfile.ZIP_DEFLATED)
        else: print('missing', f)
sz = os.path.getsize(out); print(out, round(sz / 1e6), 'MB', len(files), 'files')
