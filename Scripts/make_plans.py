import numpy as np, re, csv, os
T=[0,2,4,6,7,8,8.5,9,9.5,9.75,10,10.5,11,11.5,11.75,12,12.5,13,13.5,14,16,20,24]
F=[0,.022,.048,.080,.098,.120,.133,.147,.163,.172,.181,.204,.235,.283,.357,.663,.735,.772,.799,.820,.880,.952,1.0]
dt=5/60
def hyeto(P,dur):
    if dur==6:
        t=np.arange(0,6+1e-9,dt); f=np.interp(9+t,T,F); f=(f-f[0])/(f[-1]-f[0])
    else:
        t=np.arange(0,24+1e-9,dt); f=np.interp(t,T,F)
    cum=P*f; return np.concatenate([[0.0],np.diff(cum)]), t, cum   # leading 0: RAS ignores t=0 ordinate
STORMS=[ # (num, rp, dur, depth, sim_end)
 (3,2,6,2.32,'01JAN2026,1200'),(4,10,6,3.33,'01JAN2026,1200'),(5,25,6,3.96,'01JAN2026,1200'),(6,100,6,4.99,'01JAN2026,1200'),
 (7,10,24,4.76,'02JAN2026,0600'),(8,100,24,7.47,'02JAN2026,0600')]
u01=open('ValleyCreek.u01','rb').read().decode('latin-1').split('\r\n')
p01=open('ValleyCreek.p01','rb').read().decode('latin-1').split('\r\n')
hi=[i for i,l in enumerate(u01) if l.startswith('Precipitation Hydrograph=')][0]
he=hi+1
while he<len(u01) and '=' not in u01[he]: he+=1
os.makedirs('GIS/Design_Storms',exist_ok=True)
for n,rp,dur,P,end in STORMS:
    inc,t,cum=hyeto(P,dur)
    lines=[''.join(f'{x:8.4f}' for x in inc[i:i+10]) for i in range(0,len(inc),10)]
    title=f'{rp}yr {dur}hr SCS Type II (Atlas14 {P:.2f}in)'
    u=list(u01); u[0]='Flow Title='+title
    u=u[:hi]+[f'Precipitation Hydrograph= {len(inc)} ']+lines+u[he:]
    open(f'ValleyCreek.u{n:02d}','wb').write('\r\n'.join(u).encode('latin-1'))
    p=list(p01)
    for i,l in enumerate(p):
        if l.startswith('Plan Title='): p[i]=f'Plan Title={rp}yr {dur}hr Type II Rain-on-Grid'
        elif l.startswith('Short Identifier='): p[i]=f'Short Identifier={rp}yr{dur}hr'
        elif l.startswith('Simulation Date='): p[i]=f'Simulation Date=01JAN2026,0000,{end}'
        elif l.startswith('Flow File='): p[i]=f'Flow File=u{n:02d}'
    open(f'ValleyCreek.p{n:02d}','wb').write('\r\n'.join(p).encode('latin-1'))
    with open(f'GIS/Design_Storms/Design_Storm_{rp}yr_{dur}hr_TypeII.csv','w',newline='') as fh:
        w=csv.writer(fh); w.writerow(['time_hr','incremental_in','cumulative_in'])
        for i in range(1,len(inc)): w.writerow([round(i*dt,4),round(inc[i],4),round(cum[i],4)])
    print(n,title,len(inc),round(inc.sum(),3),'peak 5-min',inc.max(),end)
# project file
pr=open('ValleyCreek.prj','rb').read().decode('latin-1').split('\r\n')
iu=max(i for i,l in enumerate(pr) if l.startswith('Unsteady File='))
pr=pr[:iu+1]+[f'Unsteady File=u{n:02d}' for n,*_ in STORMS if f'Unsteady File=u{n:02d}' not in pr]+pr[iu+1:]
ip=max(i for i,l in enumerate(pr) if l.startswith('Plan File='))
pr=pr[:ip+1]+[f'Plan File=p{n:02d}' for n,*_ in STORMS if f'Plan File=p{n:02d}' not in pr]+pr[ip+1:]
open('ValleyCreek.prj','wb').write('\r\n'.join(pr).encode('latin-1'))
