"""Keep the NEER West Whiteland project's gauges current.

- NOAA/NWS river forecasts (NWPS) for DWNP1 and VFGP1 -> stage readings on the
  'NWS forecast <LID>' sensor sites, plus a plain-language forecast line on the
  'NOAA river forecast gauges' layer.
- USGS gauges in the 'USGS stream gauges - Exton area' layer -> last 3 days refetched.

Needs NEER_API_KEY in the environment. Safe to run as often as every 15 minutes.
"""
import json, os, time, urllib.request, urllib.error

BASE = 'https://api.neer.ai/v1'
PROJECT = 'cc13e63f-2eae-41b3-a3cc-76bc82edaa66'
NOAA_LAYER = 'd1a3748c-2ea3-4c45-ba8c-5157186f45cd'
USGS_LAYER = 'dc609e79-a1cb-41d4-bc6f-92e4fc89857b'
NWS = {'DWNP1': {'site': '81320ce9-d3bb-4dff-925e-5170970cabd3', 'fid': 1},
       'VFGP1': {'site': '579cff15-81ac-43d5-a306-37dfd951278c', 'fid': 2}}
KEY = os.environ['NEER_API_KEY'].strip()


def api(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            t = r.read(); return json.loads(t) if t else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{method} {path} -> {e.code}: {e.read().decode()[:500]}')


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r: return json.load(r)


def ms(iso): return int(time.mktime(time.strptime(iso[:19], '%Y-%m-%dT%H:%M:%S')) * 1000 - time.timezone * 1000)


feats = {r['fid']: r for r in api('GET', f'/layers/{NOAA_LAYER}/features?limit=50')['rows']}
changes = []
for lid, cfg in NWS.items():
    sf = get(f'https://api.water.noaa.gov/nwps/v1/gauges/{lid}/stageflow')
    fc = sf.get('forecast') or {}
    pts = [[ms(d['validTime']), d['primary']] for d in (fc.get('data') or []) if d.get('primary') not in (None, -999)]
    if pts:
        tok = api('POST', f"/sensors/{cfg['site']}/readings/upload", {'measure': 'stage', 'unit': 'ft', 'points': pts})
        api('POST', f"/sensors/{cfg['site']}/readings", {'measure': 'stage', 'unit': 'ft', 'inputToken': tok['inputToken']})
        peak = max(pts, key=lambda p: p[1])
        p = feats[cfg['fid']]['properties']
        cat = ('MAJOR flood' if peak[1] >= p['major_flood_ft'] else 'MODERATE flood' if peak[1] >= p['moderate_flood_ft'] else
               'MINOR flood' if peak[1] >= p['minor_flood_ft'] else 'Action stage' if peak[1] >= p['action_stage_ft'] else 'below flood stage')
        note = (f"NWS forecast issued {fc.get('issuedTime', '')[:16].replace('T', ' ')} UTC: crest {peak[1]:.1f} ft "
                f"at {time.strftime('%a %d %b %H:%M', time.gmtime(peak[0] / 1000))} UTC ({cat})")
    else:
        note = 'No NWS forecast issued right now (NWS issues one here only when high water is expected)'
    old = feats[cfg['fid']]['properties'].get('forecast_note')
    if note != old:
        changes.append({'fid': cfg['fid'], 'set': {'forecast_note': note}, 'was': {'forecast_note': old}})
    print(lid, len(pts), 'forecast points |', note)
if changes:
    api('POST', f'/layers/{NOAA_LAYER}/edits', {'changes': changes})

now = int(time.time() * 1000)
for s in api('GET', f'/sensors?projectId={PROJECT}')['sites']:
    if s['layerId'] == USGS_LAYER:
        api('POST', f"/sensors/{s['id']}/fetch", {'start': now - 3 * 86400 * 1000, 'end': now})
        print('USGS', s['externalId'], 'refetch queued')
