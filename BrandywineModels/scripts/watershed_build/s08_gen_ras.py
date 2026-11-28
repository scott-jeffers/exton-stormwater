"""Write a HEC-RAS 7.0.1 rain-on-grid project from the Exton (ValleyCreek) templates.
Plans: p01-p05 6-hr storms (2,5,10,25,100); p06-p11 24-hr WARM-UPS (0-3 h, Courant 1, write IC at end);
p12-p17 24-hr storms (2,5,10,25,50,100) restarting from the warm-up at 03:00. Warm-ups come first so
Run Multiple Plans (plan-number order) works in one pass.
Usage: s08_gen_ras.py <outdir> <ProjName> <SAName> <ProjTitle> <atlas14.json> <work dir with perimeter/bcline/mesh_points>"""
import sys, os, json, csv, shutil, numpy as np, geopandas as gpd

OUT, NAME, SAN, TITLE, ATLAS, WD = sys.argv[1:7]
TPL = '/home/claude/ebb/tpl/ValleyCreek.'
SA = f'{SAN:<16}'
os.makedirs(OUT, exist_ok=True); os.makedirs(f'{OUT}/GIS/Design_Storms', exist_ok=True); os.makedirs(f'{OUT}/Terrain', exist_ok=True)
rd = lambda ext: open(TPL + ext, 'rb').read().decode('latin-1').replace('\r\n', '\n').split('\n')
wr = lambda path, lines: open(path, 'wb').write('\r\n'.join(lines).encode('latin-1'))

per = gpd.read_file(f'{WD}/perimeter.gpkg').geometry.iloc[0]
bcg = gpd.read_file(f'{WD}/bcline.gpkg'); bc = bcg.geometry.iloc[0]; slope = float(bcg.slope.iloc[0])
pts = np.load(f'{WD}/mesh_points.npy')

def pairs(coords, per_line):
    vals = [v for xy in coords for v in xy]
    return [''.join(f'{v:>16.6f}'[-16:] for v in vals[i:i + per_line]) for i in range(0, len(vals), per_line)]

# ---------------- geometry (same layout as Exton's final g01: 2D area + BC line, culverts burned into terrain)
x0, y0, x1, y1 = per.bounds; c = per.centroid
G = [f'Geom Title={TITLE} 2D Rain-on-Grid (culverts burned)', 'Program Version=7.01',
     f'Viewing Rectangle= {x0:.2f} , {x1:.2f} , {y1:.2f} , {y0:.2f} ', '', f'Storage Area={SA},{c.x:.4f},{c.y:.4f}']
pc = list(per.exterior.coords)
G.append(f'Storage Area Surface Line= {len(pc)} '); G += pairs([p[:2] for p in pc], 2)
G += ['Storage Area Type= 1 ', 'Storage Area Area=', 'Storage Area Min Elev=', 'Storage Area Is2D=-1', 'Storage Area Point Generation Data=,,80,80',
      f'Storage Area 2D Points= {len(pts)} ']
G += pairs([tuple(p) for p in pts], 4)
G += ['Storage Area 2D PointsPerimeterTime=24Nov2026 12:00:00', 'Storage Area Mannings=0.06',
      '2D Cell Volume Filter Tolerance=0.01', '2D Cell Minimum Area Fraction=0.01', '2D Face Profile Filter Tolerance=0.01',
      '2D Face Area Elevation Profile Filter Tolerance=0.01', '2D Face Area Elevation Conveyance Ratio=0.02', '2D Face Min Length Ratio=0.05',
      '2D Face Area Laminar Depth=0.2', '2D Multiple Face Mann n=0', '2D Composite LC=0', '']
bcc = list(bc.coords); m = bc.interpolate(0.5, normalized=True)
G += [f"BC Line Name={'Outlet':<32}", f'BC Line Storage Area={SA}', f'BC Line Start Position= {bcc[0][0]} , {bcc[0][1]} ',
      f'BC Line Middle Position= {m.x} , {m.y} ', f'BC Line End Position= {bcc[-1][0]} , {bcc[-1][1]} ', f'BC Line Arc= {len(bcc)} ']
G += pairs([p[:2] for p in bcc], 4)
G += ['BC Line Text Position= 1.79769313486232E+308 , 1.79769313486232E+308 ', 'LCMann Time=Dec/30/1899 00:00:00',
      'LCMann Region Time=Dec/30/1899 00:00:00', 'LCMann Table=0', 'Chan Stop Cuts=-1 ', '', '', '', 'Use User Specified Reach Order=0',
      'GIS Ratio Cuts To Invert=-1', 'GIS Limit At Bridges=0', 'Composite Channel Slope=5', '']
wr(f'{OUT}/{NAME}.g01', G)

# ---------------- storms (NRCS Type II, 5-min, Atlas 14 at watershed centroid)
A = json.load(open(ATLAS)); Q = A['quantiles']; durs = A['durations']; rps = A['rps']
depth = lambda rp, d: float(Q[durs.index(f'{d}-hr')][rps.index(rp)])
T = [0, 2, 4, 6, 7, 8, 8.5, 9, 9.5, 9.75, 10, 10.5, 11, 11.5, 11.75, 12, 12.5, 13, 13.5, 14, 16, 20, 24]
F = [0, .022, .048, .080, .098, .120, .133, .147, .163, .172, .181, .204, .235, .283, .357, .663, .735, .772, .799, .820, .880, .952, 1.0]
dt = 5 / 60
def hyeto(P, dur):
    t = np.arange(0, dur + 1e-9, dt)
    f = np.interp(9 + t, T, F) if dur == 6 else np.interp(t, T, F)
    f = (f - f[0]) / (f[-1] - f[0]); cum = P * f
    return np.concatenate([[0.0], np.diff(cum)]), cum
U6, U24, U24w = rd('u01'), rd('u07'), rd('u13')
P6, P24, P24w = rd('p01'), rd('p07'), rd('p13')

def flow_file(tpl, title, inc, restart=None):
    u = list(tpl); hi = [i for i, l in enumerate(u) if l.startswith('Precipitation Hydrograph=')][0]; he = hi + 1
    while he < len(u) and '=' not in u[he]: he += 1
    u = u[:hi] + [f'Precipitation Hydrograph= {len(inc)} '] + [''.join(f'{x:8.4f}' for x in inc[i:i + 10]) for i in range(0, len(inc), 10)] + u[he:]
    out = []
    for l in u:
        if l.startswith('Flow Title='): l = 'Flow Title=' + title
        elif l.startswith('Restart Filename='): l = f'Restart Filename={NAME}.{restart}.01JAN2026 0300.rst'
        elif l.startswith('Boundary Location='):
            parts = l.split(','); parts[5] = SA; l = ','.join(parts)
        elif l.startswith('Friction Slope='): l = f'Friction Slope={slope:.4f}'
        out.append(l)
    return out

def plan_file(tpl, title, short, sim, flow):
    out = []
    for l in tpl:
        if l.startswith('Plan Title='): l = 'Plan Title=' + title
        elif l.startswith('Short Identifier='): l = 'Short Identifier=' + short
        elif l.startswith('Simulation Date='): l = 'Simulation Date=' + sim
        elif l.startswith('Flow File='): l = 'Flow File=' + flow
        elif l.startswith('UNET D2 Name='): l = f'UNET D2 Name={SA}'
        out.append(l)
    return out

plans = []
for k, rp in enumerate((2, 5, 10, 25, 100), start=1):
    P = depth(rp, 6); inc, cum = hyeto(P, 6); n = f'{k:02d}'
    wr(f'{OUT}/{NAME}.u{n}', flow_file(U6, f'{rp}yr 6hr SCS Type II (Atlas14 {P:.2f}in)', inc))
    wr(f'{OUT}/{NAME}.p{n}', plan_file(P6, f'{rp}yr 6hr Type II Rain-on-Grid', f'{rp}yr6hr', '01JAN2026,0000,01JAN2026,1200', 'u' + n))
    plans.append((n, f'{rp}yr 6hr Type II Rain-on-Grid', rp, 6, P, inc, cum))
for k, rp in enumerate((2, 5, 10, 25, 50, 100)):
    P = depth(rp, 24); inc, cum = hyeto(P, 24); nw = f'{6 + k:02d}'; nm = f'{12 + k:02d}'
    wr(f'{OUT}/{NAME}.u{nw}', flow_file(U24w, f'{rp}yr 24hr SCS Type II (Atlas14 {P:.2f}in) [warm-up 0-3h]', inc))
    wr(f'{OUT}/{NAME}.p{nw}', plan_file(P24w, f'{rp}yr 24hr Type II Rain-on-Grid WARMUP 0-3h', f'W{rp}yr24hr', '01JAN2026,0000,01JAN2026,0300', 'u' + nw))
    wr(f'{OUT}/{NAME}.u{nm}', flow_file(U24, f'{rp}yr 24hr SCS Type II (Atlas14 {P:.2f}in)', inc, restart='p' + nw))
    wr(f'{OUT}/{NAME}.p{nm}', plan_file(P24, f'{rp}yr 24hr Type II Rain-on-Grid', f'{rp}yr24hr', '01JAN2026,0300,02JAN2026,0600', 'u' + nm))
    plans.append((nw, f'{rp}yr 24hr WARMUP', rp, 24, P, inc, cum)); plans.append((nm, f'{rp}yr 24hr Type II Rain-on-Grid', rp, 24, P, inc, cum))
for n, title, rp, dur, P, inc, cum in plans:
    if 'WARMUP' in title: continue
    with open(f'{OUT}/GIS/Design_Storms/Design_Storm_{rp}yr_{dur}hr_TypeII.csv', 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['time_hr', 'incremental_in', 'cumulative_in'])
        for i in range(1, len(inc)): w.writerow([round(i * dt, 4), round(inc[i], 4), round(cum[i], 4)])

# ---------------- project
pr = rd('prj'); out = []
for l in pr:
    if l.startswith('Proj Title='): l = f'Proj Title={TITLE}'
    elif l.startswith('Current Plan='): l = 'Current Plan=p01'
    out.append(l)
wr(f'{OUT}/{NAME}.prj', out)
shutil.copy('/home/claude/ebb/tpl/Projection.prj' if os.path.exists('/home/claude/ebb/tpl/Projection.prj') else '/dev/null', f'{OUT}/Terrain/Projection.prj')
print(NAME, 'cells', len(pts), 'plans', len(plans), 'BC slope', round(slope, 5))
for n, title, rp, dur, P, inc, cum in plans: print(' p' + n, title, f'{P:.2f} in')
