import numpy as np, json
# NRCS Type II 24-hr cumulative distribution (TR-20/TR-55 ordinates, 0.5-hr with finer values near peak)
T=[0,2,4,6,7,8,8.5,9,9.5,9.75,10,10.5,11,11.5,11.75,12,12.5,13,13.5,14,16,20,24]
F=[0,.022,.048,.080,.098,.120,.133,.147,.163,.172,.181,.204,.235,.283,.357,.663,.735,.772,.799,.820,.880,.952,1.0]
P6=2.88  # NOAA Atlas 14 Vol 2 v3, 5-yr 6-hr, watershed centroid 40.0176N 75.6346W
dt=5/60
t=np.arange(0,6+1e-9,dt)
f=np.interp(9+t,T,F); f=(f-f[0])/(f[-1]-f[0])
cum=P6*f; inc=np.diff(cum)
print(len(inc),inc.sum(),inc.max()/dt,"in/hr peak 5-min")
json.dump({"interval_min":5,"incremental_in":[round(x,4) for x in inc]},open("storm.json","w"))
import csv
with open("proj/ValleyCreek/GIS/Design_Storm_5yr_6hr_TypeII.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["time_hr","incremental_in","cumulative_in"])
    for i,x in enumerate(inc): w.writerow([round((i+1)*dt,4),round(x,4),round(cum[i+1],4)])
