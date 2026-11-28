"""Fill a downstream model's inflow hydrographs from upstream models' outlet results (same storm, same clock).
Usage: s10_inflows.py <proj dir> <ProjName> <BCname>=<outflows.json> [...]
outflows.json: {planNN: {title, sim, q (5-min cfs), t0}} as extracted from the upstream pNN.hdf files.
Storms are matched by return period, duration and warm-up/main. Missing upstream results stay at zero and are reported."""
import sys, re, glob, json
from datetime import datetime, timedelta
PD, NAME = sys.argv[1], sys.argv[2]
ups = {a.split('=')[0]: json.load(open(a.split('=')[1])) for a in sys.argv[3:]}
def key(title):
    m = re.search(r'(\d+)yr (\d+)hr', title); w = bool(re.search('warm', title, re.I))
    return (int(m.group(1)), int(m.group(2)), w) if m else None
ts = lambda s: datetime.strptime(s, '%d%b%Y %H:%M:%S')
report = []
for uf in sorted(glob.glob(f'{PD}/{NAME}.u??')):
    L = open(uf, 'rb').read().decode('latin-1').split('\r\n')
    title = L[0].split('=', 1)[1]; k = key(title)
    pf = uf.replace('.u', '.p'); sim = [l for l in open(pf, encoding='latin-1') if l.startswith('Simulation Date=')][0].split('=')[1].strip().split(',')
    t0 = datetime.strptime(sim[0] + ' ' + sim[1], '%d%b%Y %H%M')
    for bc, data in ups.items():
        i = [j for j, l in enumerate(L) if l.startswith('Boundary Location=') and l.split(',')[7].strip() == bc]
        if not i: continue
        i = i[0]; n = int(L[i + 2].split('=')[1]); e = i + 3
        while '=' not in L[e]: e += 1
        if 'Ida' in title: src = [v for v in data.values() if v.get('q') and v.get('title') and 'Ida' in v['title']]
        else: src = [v for v in data.values() if v.get('q') and v.get('title') and k and key(v['title']) == k]
        if not src and k:   # e.g. a 24-hr storm run 0-30 h in one go: use it for the warm-up window too
            src = [v for v in data.values() if v.get('q') and v.get('title') and key(v['title']) and key(v['title'])[:2] == k[:2] and ts(v['t0']) <= t0]
        if src:
            s = src[0]; off = int(round((t0 - ts(s['t0'])).total_seconds() / 300)); q = s['q'][max(off, 0):]
            if q and len(q) < n:   # extend past the upstream run's end with its own recession rate
                r = min(1.0, (q[-1] / q[-13]) ** (1 / 12)) if len(q) > 13 and q[-13] > 0 else 1.0
                ext = [q[-1] * r ** (j + 1) for j in range(n - len(q))]; q = q + ext
            q = q[:n] if q else [0.0] * n
            status = f'filled (peak {max(q):.0f} cfs)'
        else:
            q = [0.0] * n; status = 'NO UPSTREAM RESULT - zero'
        L = L[:i + 3] + [''.join(f'{v:8.1f}' for v in q[j:j + 10]) for j in range(0, n, 10)] + L[e:]
        report.append((uf.split('.')[-1], title, bc, status))
    open(uf, 'wb').write('\r\n'.join(L).encode('latin-1'))
for r in report: print(*r, sep=' | ')
