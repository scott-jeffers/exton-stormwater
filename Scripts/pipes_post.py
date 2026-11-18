import geopandas as gpd, numpy as np, networkx as nx
pf=gpd.read_file("pipe_links.gpkg"); nodes=gpd.read_file("pipe_nodes.gpkg")
D=nx.DiGraph()
for i,r in pf.iterrows(): D.add_edge(r.up,r.dn,i=i)
order=list(nx.topological_sort(D))
# cap: pipe size not larger than smallest GIS-known size downstream
known=pf.dia_src!='inferred (Rational Q10 + Manning full-flow)'
cap={}
for n in reversed(order):
    outs=[D[n][v]['i'] for v in D.successors(n)]
    c=np.inf
    for i in outs:
        v=pf.at[i,'dn']; ci=cap.get(v,np.inf)
        if known[i]: ci=min(ci,pf.at[i,'D'])
        c=min(c,ci)
    cap[n]=c
capped=0
for i,r in pf.iterrows():
    c=cap.get(r.dn,np.inf)
    if not known[i] and r.D>c: pf.at[i,'D']=c; capped+=1
# then enforce non-decreasing downstream for inferred pipes
for n in order:
    ins=[D[u][n]['i'] for u in D.predecessors(n)]
    mx=max([pf.at[i,'D'] for i in ins] or [0])
    for v in D.successors(n):
        i=D[n][v]['i']
        if not known[i] and pf.at[i,'D']<mx and mx<=cap.get(v,np.inf): pf.at[i,'D']=mx
pf['slope']=(pf.up_inv-pf.dn_inv)/pf.L
pf['qa']=''
pf.loc[pf.slope<0.002,'qa']+='flat(<0.2%);'
cov=[nodes.set_index('nid').rim[u]-(iu+d) for u,iu,d in zip(pf.up,pf.up_inv,pf.D)]
pf['cover_up']=cov; pf.loc[pf.cover_up<1,'qa']+='low cover;'
pf.to_file("pipe_links.gpkg")
print("capped",capped); print(pf.D.value_counts().sort_index()); print(pf.qa.value_counts())
print(pf.dia_src.value_counts())
