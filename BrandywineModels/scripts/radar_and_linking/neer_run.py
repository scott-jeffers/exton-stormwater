import json, os, sys, time, urllib.request, urllib.error
BASE='https://api.neer.ai/v1'; KEY=os.environ['NEER_API_KEY']  # set your own NEER API key
def api(m,p,b=None):
    r=urllib.request.Request(BASE+p,method=m,data=None if b is None else json.dumps(b).encode(),headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(r,timeout=300) as x: t=x.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e: raise RuntimeError(f'{m} {p} -> {e.code}: {e.read().decode()[:2000]}')
def upload(path):
    u=api('POST','/uploads',{'name':os.path.basename(path),'size':os.path.getsize(path)})
    parts=[]
    with open(path,'rb') as f:
        for p in u['parts']:
            data=f.read(u['partSize'])
            for attempt in range(4):
                try:
                    import requests
                    r=requests.put(p['url'],data=data,timeout=900); r.raise_for_status()
                    parts.append({'number':p['number'],'etag':r.headers['ETag']}); break
                except Exception as e:
                    if attempt==3: raise
                    time.sleep(5)
    return {'upload':u['upload'],'parts':parts}
if __name__=='__main__':
    zp, plans, size = sys.argv[1], sys.argv[2].split(','), (sys.argv[3] if len(sys.argv)>3 else 'standard')
    inp=upload(zp); print('uploaded',zp, len(inp['parts']),'parts')
    jobs=json.load(open('jobs.json')) if os.path.exists('jobs.json') else {}
    for i,pl in enumerate(plans):
        if i>0:
            try: pass
            except Exception: pass
        name=f"{os.path.basename(zp)[:-4]} {pl}"
        try: r=api('POST','/simulations',{'type':'hecras','input':inp,'planNumber':pl,'computeSize':size,'engineVersion':'7.0.1','preprocess':True,'name':name})
        except RuntimeError as e:
            print('reuse failed, re-uploading:',str(e)[:200]); inp=upload(zp)
            r=api('POST','/simulations',{'type':'hecras','input':inp,'planNumber':pl,'computeSize':size,'engineVersion':'7.0.1','preprocess':True,'name':name})
        sid=r.get('created',{}).get('id') if isinstance(r.get('created'),dict) else r.get('created') or r.get('id')
        print(name,'->',json.dumps(r)[:400]); jobs[name]={'id':sid,'resp':r}
        json.dump(jobs,open('jobs.json','w'),indent=1)
