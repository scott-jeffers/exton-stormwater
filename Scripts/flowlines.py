import numpy as np, geopandas as gpd, rasterio, pyflwdir
from shapely.geometry import LineString
ds=rasterio.open("dem10_enf.tif"); a=ds.read(1)
fl=pyflwdir.from_dem(a,nodata=-9999,transform=ds.transform,latlon=False,outlets="edge")
up=fl.upstream_area("cell")*100/43560  # acres
feats=fl.streams(mask=up>=8, uparea=up)   # list of geojson-like features
gdf=gpd.GeoDataFrame.from_features(feats,crs=2272)
ws=gpd.read_file("watershed.gpkg").geometry.iloc[0]
gdf=gdf[gdf.intersects(ws)]
print(len(gdf), gdf.columns.tolist(), gdf.length.sum()/5280)
gdf.to_file("flowlines.gpkg")
