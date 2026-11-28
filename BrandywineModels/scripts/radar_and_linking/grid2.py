import warnings, sys; warnings.filterwarnings('ignore')
import pandas as pd, glob, logging; logging.disable(logging.INFO)
from ras_commander import init_ras_project, RasUnsteady
d,nm=sys.argv[1:3]
r=init_ras_project(d,'7.0')
fs=sorted(glob.glob('tif2/ida_*.tif'))
ts=[pd.Timestamp('2026-01-01 00:00')+pd.Timedelta(hours=k) for k in range(1,23)]
RasUnsteady.set_gridded_precipitation_geotiff(f'{d}/{nm}.u19',fs,timestamps=ts,units='in',value_type='amount',first_timestep_hours=1,historic=True,interpolation='Bilinear',ras_object=r)
print('done',d)
