"""Per-cell max WSE + dam/outlet summaries from a RAS plan hdf -> small npz/json."""
import sys, h5py, numpy as np, json
src, area, out = sys.argv[1:4]
f = h5py.File(src, 'r')
g = f[f'Geometry/2D Flow Areas/{area}']
n = int(f['Geometry/2D Flow Areas/Attributes'][()]['Cell Count'][0]) if 'Cell Count' in f['Geometry/2D Flow Areas/Attributes'].dtype.names else None
xy = g['Cells Center Coordinate'][()]; zmin = g['Cells Minimum Elevation'][()]
s = f[f'Results/Unsteady/Output/Output Blocks/Base Output/Summary Output/2D Flow Areas/{area}/Maximum Water Surface'][()]
wse = s[0]; tmax = s[1] if s.shape[0] > 1 else None
n = n or len(wse)
np.savez_compressed(out + '.npz', xy=xy[:n].astype('float32'), zmin=zmin[:n].astype('float32'), wse=wse[:n].astype('float32'), tmax=(tmax[:n].astype('float32') if tmax is not None else np.zeros(n, 'float32')))
b = 'Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
summ = {'title': f['Plan Data/Plan Information'].attrs['Plan Title'].decode(), 'dams': {}, 'bc': {}}
t = f['Results/Summary/Compute Messages (text)'][()]; t = t[0] if not isinstance(t, bytes) else t; t = t.decode('latin-1')
i = t.find('Overall Volume Accounting Error as percentage:'); summ['vol_err_pct'] = float(t[i:i+80].split(':')[1].split()[0]) if i >= 0 else None
i = t.find('Unsteady Flow Computations\t'); summ['runtime'] = t[i:i+60].split('\t')[1].split()[0] if i >= 0 else None
if 'SA 2D Area Conn' in f[b]:
    for k in f[b + 'SA 2D Area Conn'].keys():
        a = f[b + f'SA 2D Area Conn/{k}/Structure Variables'][()]; c = f[b + f'SA 2D Area Conn/{k}/Culvert Groups/Spillway'][()]
        summ['dams'][k.split()[-1]] = dict(q_total=round(float(np.abs(a[:, 0]).max())), q_weir=round(float(np.abs(a[:, 1]).max())), q_culv=round(float(c[:, 0].max())), pool_max=round(float(c[:, 1].max()), 2), pool_t=c[:, 1].round(2).tolist(), q_t=np.abs(a[:, 0]).round(0).tolist())
for k in f[b + 'Boundary Conditions'].keys():
    if 'per Face' in k: continue
    v = f[b + f'Boundary Conditions/{k}'][()]; summ['bc'][k] = np.abs(v[:, 1]).round(1).tolist()
summ['times_hr'] = [round(x * 1.0, 3) for x in (np.arange(len(next(iter(summ['bc'].values())))) * 10 / 60)]
json.dump(summ, open(out + '.json', 'w'))
print(out, len(wse), 'cells; maxdepth>1ft cells', int(((wse - zmin[:len(wse)]) > 1).sum()), summ['vol_err_pct'], summ['runtime'])
