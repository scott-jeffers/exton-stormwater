"""Extract each plan's outlet hydrograph (5-min cfs) from a project's pNN.hdf results.
Usage: extract_outflows.py <proj dir> <ProjName> <out.json>"""
import sys, glob, json, h5py, numpy as np
from datetime import datetime, timedelta
PD, NAME, OUT = sys.argv[1:4]; res = {}
for f in sorted(glob.glob(f'{PD}/{NAME}.p[0-9][0-9].hdf')):
    try:
        h = h5py.File(f, 'r'); b = 'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
        title = h['Plan Data/Plan Information'].attrs['Plan Title'].decode()
        ds = h[b + 'Boundary Conditions/Outlet']; v = ds[()]
        cols = [c[0].decode() if hasattr(c[0], 'decode') else str(c[0]) for c in ds.attrs.get('Variable_Unit', [])]
        qi = cols.index('Flow') if 'Flow' in cols else 1
        q = np.abs(v[:, qi]); tt = [datetime.strptime(s.decode(), '%d%b%Y %H:%M:%S') for s in h[b + 'Time Date Stamp'][()]]
        t = np.array([(x - tt[0]).total_seconds() for x in tt]); t5 = np.arange(0, t[-1] + 1, 300)
        res[f.split('.')[-2]] = dict(title=title, t0=tt[0].strftime('%d%b%Y %H:%M:%S'), q=[round(float(x), 1) for x in np.interp(t5, t, q)])
        print(f.split('/')[-1], title, 'peak', round(float(q.max())))
    except Exception as e:
        print(f.split('/')[-1], 'no results:', e)
json.dump(res, open(OUT, 'w'))
