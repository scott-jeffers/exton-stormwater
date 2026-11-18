import py7zr,os
p=os.path.expanduser("~/mnt/Exton-Model/Chesco GIS/MS4_BaseGISData_11212016.mpk")
with py7zr.SevenZipFile(p) as z:
    t=[n for n in z.getnames() if n.startswith('v103') or n.startswith('esriinfo')]
    z.extract(path="mpk",targets=t)
print("done")
