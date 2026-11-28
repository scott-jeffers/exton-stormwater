"""Lengthen the 10-yr 6-hr plan (p03/u03) to 24 h and add an Ida plan (p18/u18, 30 h) to each Brandywine model.
Run from EBBrandywine-Model. Idempotent."""
import os, re, shutil
M = {  # folder, name, Ida 6-hr depth (in) from Brandywine Flood Study gauges
 'M03': ('Upper_EB_Marsh_HECRAS', 'UpperEBMarsh', 5.6),   # Glenmoore 4.99, Chester Springs 6.18
 'M12': ('BuckDoeRun_HECRAS', 'BuckDoeRun', 6.4),          # Modena 7.02, Chambers Lake 5.82
 'M02': ('Downingtown_HECRAS', 'Downingtown', 5.9),        # EB below Downingtown 5.83, Chester Springs 6.18
 'M04': ('WBCoatesville_HECRAS', 'WBCoatesville', 6.4),    # Chambers Lake 5.82, Modena 7.02
 'M05': ('BrandywineMain_HECRAS', 'BrandywineMain', 4.3),  # Marshallton 5.25, Chadds Ford 3.28
}
rd = lambda p: open(p, 'rb').read().decode('latin-1').split('\r\n')
wr = lambda p, L: open(p, 'wb').write('\r\n'.join(L).encode('latin-1'))
def pad_flows(L, n_new):
    out = []; i = 0
    while i < len(L):
        l = L[i]
        if l.startswith('Flow Hydrograph='):
            n = int(l.split('=')[1]); v = []; k = i + 1
            while len(v) < n: v += [float(L[k][a:a+8]) for a in range(0, len(L[k]), 8) if L[k][a:a+8].strip()]; k += 1
            v = (v + [v[-1]] * n_new)[:n_new]
            out += [f'Flow Hydrograph= {n_new} '] + [''.join(f'{x:8.1f}' for x in v[j:j+10]) for j in range(0, n_new, 10)]
            i = k; continue
        out.append(l); i += 1
    return out
for m, (fd, nm, ida) in M.items():
    P = f'{fd}/{nm}'; os.makedirs(f'{fd}/Backup/pre_neer', exist_ok=True)
    for ext in ('p03', 'u03', 'prj'):
        b = f'{fd}/Backup/pre_neer/{nm}.{ext}'
        if not os.path.exists(b): shutil.copy2(f'{P}.{ext}', b)
    # 10-yr: 24 h
    L = rd(f'{P}.p03'); L = [('Simulation Date=01JAN2026,0000,02JAN2026,0000' if l.startswith('Simulation Date=') else l) for l in L]; wr(f'{P}.p03', L)
    wr(f'{P}.u03', pad_flows(rd(f'{P}.u03'), 289))
    # Ida: copy, scale rain, 30 h
    L = rd(f'{P}.p03')
    L = [('Simulation Date=01JAN2026,0000,02JAN2026,0600' if l.startswith('Simulation Date=') else
          f'Plan Title=Ida 2021 6hr Rain-on-Grid ({ida:.1f} in)' if l.startswith('Plan Title=') else
          'Short Identifier=Ida2021' if l.startswith('Short Identifier=') else
          'Flow File=u18' if l.startswith('Flow File=') else l) for l in L]
    wr(f'{P}.p18', L)
    U = rd(f'{P}.u03'); i = [j for j, l in enumerate(U) if l.startswith('Precipitation Hydrograph=')][0]
    n = int(U[i].split('=')[1]); v = []; k = i + 1
    while len(v) < n: v += [float(U[k][a:a+8]) for a in range(0, len(U[k]), 8) if U[k][a:a+8].strip()]; k += 1
    f = ida / sum(v); v = [x * f for x in v]
    U = U[:i + 1] + [''.join(f'{x:8.4f}' for x in v[j:j+10]) for j in range(0, n, 10)] + U[k:]
    U[0] = f'Flow Title=Ida 2021 6hr SCS Type II ({ida:.2f}in, Brandywine Flood Study gauge totals)'
    wr(f'{P}.u18', pad_flows(U, 361))
    J = rd(f'{P}.prj')
    if 'Plan File=p18' not in J:
        iu = max(j for j, l in enumerate(J) if l.startswith('Unsteady File=')); J.insert(iu + 1, 'Unsteady File=u18')
        ip = max(j for j, l in enumerate(J) if l.startswith('Plan File=')); J.insert(ip + 1, 'Plan File=p18')
        wr(f'{P}.prj', J)
    print(m, 'p03 -> 24 h; p18 Ida', ida, 'in (rain scale %.3f)' % f)
