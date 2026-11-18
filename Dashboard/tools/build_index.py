import json,os,re
D=os.path.expanduser('~/mnt/Exton-Model/Dashboard/data/')
L=open(D+'model_layers.js').read(); A=json.loads(L[L.index('"atlas14":')+10:L.rindex('}')])
rps=[2,5,10,25,50,100]; durs={'6-hr':'6-hr','24-hr':'24-hr'}
cat=[]
for dn,key in durs.items():
    j=A['dur'].index(key)
    for rp in rps:
        sid=f'{rp}yr-{dn}'
        cat.append({'id':sid,'name':f'{rp}-year, {dn} storm','rp':rp,'duration':dn,'duration_hr':{'1-hr':1,'6-hr':6,'24-hr':24}[dn],
          'depth_in':A['depth'][j][A['rp'].index(rp)],'dist':'SCS Type II','kind':'rain'})
cat.insert(0,{'id':'test-1in-10min','name':'TEST burst: 1.0 in in 10 min','rp':None,'duration':'10-min','duration_hr':0.17,'depth_in':1.0,'kind':'test'})
for c in cat: c['available']=os.path.exists(D+'scenarios/'+c['id']+'.js')
open(D+'scenarios/index.js','w').write('window.SCENARIO_INDEX='+json.dumps(cat,indent=0)+';\n')
print([(c['id'],c['depth_in'],c['available']) for c in cat])
