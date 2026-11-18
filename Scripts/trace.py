import numpy as np, rasterio, sys
ds=rasterio.open("dem10ft.tif"); a=ds.read(1)
d8=np.load("d8_10.npy"); up=np.load("up10.npy")
dirs={64:(-1,0),128:(-1,1),1:(0,1),2:(1,1),4:(1,0),8:(1,-1),16:(0,-1),32:(-1,-1)}
def trace(x,y,step=200):
    r,c=ds.index(x,y); w=up[r-4:r+5,c-4:c+5]; rr,cc=np.unravel_index(np.argmax(w),w.shape); r+=rr-4;c+=cc-4
    n=0; print("start",x,y)
    while d8[r,c] in dirs:
        if n%step==0: X,Y=ds.xy(r,c); print("   ",n,int(X),int(Y),round(float(a[r,c]),1),round(float(up[r,c]),2))
        di,dj=dirs[int(d8[r,c])]; r+=di;c+=dj;n+=1
    X,Y=ds.xy(r,c); print("  end",n,int(X),int(Y),a[r,c],up[r,c],d8[r,c])
for xy in sys.argv[1:]:
    x,y=map(float,xy.split(",")); trace(x,y)
