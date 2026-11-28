"""chain.py get <job name>   -> download plan hdf, cellmax json/npz, outlet series json
   chain.py m02 | m04 | m05  -> fill inflows from finished upstream jobs, build zip, submit p19,p17,p14"""
import sys, os, json, zipfile, subprocess, requests, h5py, numpy as np
from datetime import datetime
sys.path.insert(0,'/home/claude/neerjobs'); os.chdir('/home/claude/neerjobs')
from neer_run import KEY, BASE
H={'Authorization':'Bearer '+KEY}
M='/home/claude/mrms'; OUT='/home/claude/neerjobs/out2'; os.makedirs(OUT,exist_ok=True)
PROJ={'M03':'UpperEBMarsh','M12':'BuckDoeRun','M02':'Downingtown','M04':'WBCoatesville','M05':'BrandywineMain'}
def jobs(): return json.load(open('jobs.json'))
def get(name):
    tag=name.split()[0]; pl=name.split()[1]; m=[k for k,v in PROJ.items() if v==tag][0]
    if os.path.exists(f'{OUT}/{m}_{pl}.json'): return f'{OUT}/{m}_{pl}.json'
    sid=jobs()[name]['id']; s=requests.get(f'{BASE}/simulations/{sid}',headers=H,timeout=60).json()
    if s['state']=='failed': raise SystemExit(f'{name} FAILED: {s.get("failure")}')
    if s['state'] not in ('done','completed','succeeded'): raise SystemExit(f'{name} not done: {s["state"]}')
    fs=requests.get(f'{BASE}/simulations/{sid}/files',headers=H,timeout=60).json()
    fo=[f for f in fs if f['type']=='output'][0]; zp=f'{OUT}/{m}_{pl}.zip'
    with requests.get(f'{BASE}/simulations/{sid}/files/{fo["id"]}',headers=H,stream=True,timeout=1800) as r:
        r.raise_for_status(); open(zp,'wb').writelines(r.iter_content(1<<22))
    z=zipfile.ZipFile(zp); hn=[n for n in z.namelist() if n.endswith(f'.{pl}.hdf')][0]
    hp=f'{OUT}/{m}_{pl}.hdf'; open(hp,'wb').write(z.read(hn)); os.remove(zp)
    subprocess.run(['python3','/home/claude/dash/cellmax.py',hp,tag,f'/home/claude/dash/cells/{m}_{pl}'],check=True)
    h=h5py.File(hp,'r'); b='Results/Unsteady/Output/Output Blocks/Base Output/Unsteady Time Series/'
    ds=h[b+'Boundary Conditions/Outlet']; v=ds[()]
    cols=[c[0].decode() if hasattr(c[0],'decode') else str(c[0]) for c in ds.attrs.get('Variable_Unit',[])]
    q=np.abs(v[:,cols.index('Flow') if 'Flow' in cols else 1])
    tt=[datetime.strptime(x.decode(),'%d%b%Y %H:%M:%S') for x in h[b+'Time Date Stamp'][()]]
    t=np.array([(x-tt[0]).total_seconds() for x in tt]); t5=np.arange(0,t[-1]+1,300)
    q5=[round(float(x),1) for x in np.interp(t5,t,q)]
    json.dump(q5,open(f'{OUT}/{m}_{pl}.json','w')); print(name,'peak',round(max(q5)),'n',len(q5)); h.close(); os.remove(hp)
    return f'{OUT}/{m}_{pl}.json'
def fill(u,bc,src):
    subprocess.run(['python3',f'{M}/fill_u.py',u,bc,src,'433'],check=True)
def build_submit(m,plans):
    nm=PROJ[m]; base=f'zips/{nm}_base.zip'; out=f'zips/n/{nm}.zip'; os.makedirs('zips/n',exist_ok=True)
    adds=[]
    for p in plans:
        n=p[1:]
        d=f'{M}/proj/{m}' if p=='p19' else f'{M}/proj24'
        adds+=[f'{d}/{nm}.{p}={nm}/{nm}.{p}', f'{d}/{nm}.u{n}={nm}/{nm}.u{n}']
        if p=='p19':
            adds.append(f'{d}/{nm}.u19.hdf={nm}/{nm}.u19.hdf')
            nc=[os.path.join(r,f) for r,_,fs in os.walk(f'{d}/Precipitation') for f in fs][0]
            adds.append(f'{nc}={nm}/'+os.path.relpath(nc,d))
    subprocess.run(['python3',f'{M}/build_zip.py',base,out,nm,','.join(plans)]+adds,check=True)
    subprocess.run(['python3','neer_run.py',out,','.join(plans)],check=True)
    os.remove(out)
if __name__=='__main__':
    a=sys.argv[1]
    if a=='get': print(get(' '.join(sys.argv[2:])))
    elif a=='m02':
        fill(f'{M}/proj/M02/Downingtown.u19','M03_Inflow',get('UpperEBMarsh p19'))
        fill(f'{M}/proj24/Downingtown.u17','M03_Inflow',get('UpperEBMarsh p17'))
        fill(f'{M}/proj24/Downingtown.u14','M03_Inflow',get('UpperEBMarsh p14'))
        build_submit('M02',['p19','p17'])
    elif a=='m04':
        fill(f'{M}/proj/M04/WBCoatesville.u19','M12_Inflow',get('BuckDoeRun p19'))
        fill(f'{M}/proj24/WBCoatesville.u17','M12_Inflow',get('BuckDoeRun p17'))
        fill(f'{M}/proj24/WBCoatesville.u14','M12_Inflow',get('BuckDoeRun p14'))
        build_submit('M04',['p19','p17','p14'])
    elif a=='mary':
        fill(f'{M}/proj24/Downingtown.u17','M03_Inflow',get('UpperEBMarsh p17'))
        import shutil; os.makedirs(f'{M}/mary',exist_ok=True)
        p=open(f'{M}/proj24/Downingtown.p17',encoding='latin-1').read().replace('Plan Title=100yr 24hr Type II Rain-on-Grid','Plan Title=100yr 24hr MaryStWetland')
        open(f'{M}/mary/Downingtown.p17','w',encoding='latin-1',newline='').write(p); shutil.copy(f'{M}/proj24/Downingtown.u17',f'{M}/mary/Downingtown.u17')
        out='zips/n/MaryWetland.zip'; os.makedirs('zips/n',exist_ok=True)
        subprocess.run(['python3',f'{M}/build_zip.py','zips/MaryWetland_base.zip',out,'Downingtown','p17',f'{M}/mary/Downingtown.p17=Downingtown/Downingtown.p17',f'{M}/mary/Downingtown.u17=Downingtown/Downingtown.u17'],check=True)
        os.makedirs('zips/n/mary',exist_ok=True); os.replace(out,'zips/n/mary/Downingtown.zip')
        b=json.load(open('jobs.json')).get('Downingtown p17')
        subprocess.run(['python3','neer_run.py','zips/n/mary/Downingtown.zip','p17'],check=True)
        j=json.load(open('jobs.json')); j['MaryWetland p17']=j.pop('Downingtown p17')
        if b: j['Downingtown p17']=b
        json.dump(j,open('jobs.json','w'),indent=1); os.remove('zips/n/mary/Downingtown.zip')
    elif a=='m05':
        for p,u in [('p19',f'{M}/proj/M05/BrandywineMain.u19'),('p17',f'{M}/proj24/BrandywineMain.u17'),('p14',f'{M}/proj24/BrandywineMain.u14')]:
            fill(u,'M02_Inflow',get(f'Downingtown {p}')); fill(u,'M04_Inflow',get(f'WBCoatesville {p}'))
        build_submit('M05',['p19','p17','p14'])
