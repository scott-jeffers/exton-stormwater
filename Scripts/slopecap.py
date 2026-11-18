# Cap conduit slopes at SMAX by adding a drop at the downstream manhole (DS offset), raw-writing HDF strings safely.
import h5py, numpy as np, sys
SMAX=float(sys.argv[2]) if len(sys.argv)>2 else 0.06
fn=sys.argv[1]
f=h5py.File(fn,'r+')
d=f['Geometry/Pipe Conduits/Attributes']; ft=d.id.get_type(); a=np.zeros(d.shape,d.dtype); d.id.read(h5py.h5s.ALL,h5py.h5s.ALL,a,mtype=ft)
n=f['Geometry/Pipe Nodes/Attributes'][:]; inv={r['Name']:r['Invert Elevation'] for r in n}
L_=a['Conduit Length']; sl=(a['US Elevation']-a['DS Elevation'])/np.maximum(L_,1e-3)
m=sl>SMAX+1e-4; cnt=0
for i in np.where(m)[0]:
    L=a['Conduit Length'][i]; us=a['US Elevation'][i]
    newds=us-SMAX*L; dsinv=inv[a['DS Node'][i]]
    if newds<dsinv: continue
    a['DS Elevation'][i]=newds; a['DS Offset'][i]=newds-dsinv; a['Slope'][i]=SMAX
    if 'DSElev' in a.dtype.names: a['DSElev'][i]=newds
    cnt+=1
d.id.write(h5py.h5s.ALL,h5py.h5s.ALL,a,mtype=ft); f.close()
print('capped',cnt,'of',m.sum())
