/* Valley Creek Flood Watch — live weather + HEC-RAS flood scenarios
   Runs as a plain web page (open index.html or host the folder). No build step. */
(function () {
'use strict';

// ------------------------------------------------------------------ config
const M = window.MODEL_LAYERS;
const CAT = window.SCENARIO_INDEX || [];
const A14 = M.atlas14;
const CENTER = [A14.lat, A14.lon];                 // watershed centroid
const WS_BBOX = [-75.684, 39.968, -75.578, 40.057]; // watershed bounds (lon/lat)
const GAUGE_BBOX = [-75.80, 39.90, -75.45, 40.15];  // a little wider than the watershed
const IEM = 'https://mesonet.agron.iastate.edu/cache/tile.py/1.0.0/';
const QPF = 'https://mapservices.weather.noaa.gov/vector/rest/services/precip/wpc_qpf/MapServer';
const NFHL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer';
const USGS = 'https://api.waterdata.usgs.gov/ogcapi/v0/collections/';
const FLOOD_EVENTS = /flood|flash|hydrolog|heavy rain|tropical|hurricane/i;

// ------------------------------------------------------------------ helpers
const WIN_LABEL = {'1h':'1 hr','6h':'6 hr','24h':'1 day','48h':'2 days','72h':'3 days','120h':'5 days','168h':'7 days'};
const $ = (id) => document.getElementById(id);
const fmtIn = (v) => (v == null || isNaN(v)) ? '–' : (v < 0.005 ? '0.00"' : v.toFixed(2) + '"');
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function getJSON(url, opts) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 20000);
  try { const r = await fetch(url, Object.assign({signal: ctl.signal}, opts || {})); if (!r.ok) throw new Error(r.status); return await r.json(); }
  finally { clearTimeout(t); }
}
function setUpdated(msg) { $('updated').textContent = msg; }

// Atlas 14: depth for a duration key -> approximate return period (years)
function returnPeriod(depth, durKey) {
  if (depth == null) return null;
  let row, j = A14.dur.indexOf(durKey); const rp = A14.rp;
  if (j >= 0) row = A14.depth[j];
  else if (durKey === '5-day') { const a = A14.depth[A14.dur.indexOf('4-day')], b = A14.depth[A14.dur.indexOf('7-day')], f = Math.log(5/4)/Math.log(7/4); row = a.map((v,i)=> Math.exp(Math.log(v) + f*(Math.log(b[i])-Math.log(v)))); }
  else return null;
  if (depth < row[0]) return {rp: 0, label: 'less than a 1-year storm'};
  for (let i = 1; i < rp.length; i++) {
    if (depth <= row[i]) {
      const f = (Math.log(depth) - Math.log(row[i-1])) / (Math.log(row[i]) - Math.log(row[i-1]));
      const y = Math.exp(Math.log(rp[i-1]) + f * (Math.log(rp[i]) - Math.log(rp[i-1])));
      return {rp: y, label: 'about a ' + niceRP(y) + '-year storm'};
    }
  }
  return {rp: 1000, label: 'more than a 1000-year storm'};
}
function niceRP(y) { if (y < 1.5) return '1'; const s=[1,2,5,10,25,50,100,200,500,1000]; let b=s[0]; for (const v of s) if (Math.abs(Math.log(v/y)) < Math.abs(Math.log(b/y))) b=v; return String(b); }

// ------------------------------------------------------------------ map + panes
const map = L.map('map', {zoomControl: true, preferCanvas: false}).setView([40.013, -75.631], 13);
map.zoomControl.setPosition('bottomright');
[['rainPane',350],['floodPane',380],['radarPane',420],['vecPane',450],['ptPane',470]].forEach(([n,z]) => { map.createPane(n).style.zIndex = z; });
map.getPane('radarPane').style.pointerEvents = 'none';
map.getPane('rainPane').style.pointerEvents = 'none';

const basemaps = {
  'Light': L.layerGroup([
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, maxNativeZoom:16, attribution:'Esri, HERE, Garmin, © OpenStreetMap contributors'}),
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, maxNativeZoom:16, pane:'shadowPane'})]),
  'Streets': L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, attribution:'Esri'}),
  'Topo': L.tileLayer('https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}', {maxZoom:16, attribution:'USGS The National Map'}),
  'Imagery': L.layerGroup([
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {maxZoom:19, attribution:'Esri, Maxar'}),
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}', {maxZoom:19}),
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {maxZoom:19})])
};
let curBase = 'Imagery'; basemaps[curBase].addTo(map);

// ------------------------------------------------------------------ static model layers
const wsLayer = L.geoJSON(M.watershed, {pane:'vecPane', interactive:false, style:{color:'#0b3d91', weight:3, fill:false, dashArray:'8 5'}}).addTo(map);
map.fitBounds(wsLayer.getBounds(), {padding:[20,20]});
const streamLayer = L.geoJSON(M.streams, {pane:'vecPane', style:{color:'#2b7bd6', weight:1.6, opacity:.85},
  onEachFeature:(f,l)=> f.properties.NAME && l.bindTooltip(f.properties.NAME,{sticky:true})}).addTo(map);
const muniLayer = L.geoJSON(M.municipalities, {pane:'vecPane', style:{color:'#6a3d9a', weight:1.5, fill:false, opacity:.7},
  onEachFeature:(f,l)=> l.bindTooltip(f.properties.name,{sticky:true})});
const pipeLayer = L.geoJSON(M.pipes, {pane:'vecPane', style:f=>({color: f.properties.qa ? '#c2410c' : '#7c3aed', weight: Math.max(1, Math.min(4, (f.properties.dia_in||15)/14)), opacity:.8}),
  onEachFeature:(f,l)=>{ const p=f.properties; l.bindPopup(`<div class="pp-t">Storm pipe ${esc(p.Name)}</div>${p.dia_in}" diameter · ${Math.round(p.Length)} ft<br>Inverts ${p.USElev} → ${p.DSElev} ft<div class="pp-m">Size source: ${esc(p.dia_src||'inferred')}${p.qa?'<br>QA flag: '+esc(p.qa):''}</div>`); }});
const outfallLayer = L.geoJSON(M.outfalls, {pane:'ptPane', pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:3,color:'#7c3aed',fillColor:'#c4b5fd',fillOpacity:1,weight:1}),
  onEachFeature:(f,l)=> l.bindTooltip('Outfall '+f.properties.Name)});
const xingBase = L.geoJSON(M.crossings, {pane:'ptPane', pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:4,color:'#334155',fillColor:'#e2e8f0',fillOpacity:1,weight:1.5}),
  onEachFeature:(f,l)=>{ const p=f.properties; l.bindPopup(`<div class="pp-t">${esc(p.kind)} ${esc(p.cid)}</div>${esc(p.road||'Road')} over ${esc(p.stream||'stream')}<br>${p.barrels>1?p.barrels+' × ':''}${esc(p.shape)} ${p.rise} ft${p.span?' × '+p.span+' ft':''}<div class="pp-m">Drainage area ${Math.round(p.da_ac||0)} ac · source: ${esc(p.src)}</div>`); }});

// ------------------------------------------------------------------ live weather layers
const tile = (id, opts) => L.tileLayer(IEM + id + '/{z}/{x}/{y}.png', Object.assign({pane:'radarPane', opacity:.75, maxNativeZoom:16, attribution:'NEXRAD/MRMS via Iowa Environmental Mesonet'}, opts||{}));
const radarNow = tile('nexrad-n0q-900913');
const rainPast = {
  '1h': tile('q2-n1p-900913', {pane:'rainPane', opacity:.7}),
  '24h': tile('q2-p24h-900913', {pane:'rainPane', opacity:.7}),
  '72h': tile('q2-p72h-900913', {pane:'rainPane', opacity:.7})
};
const qpfLayers = {'6h':[7], '24h':[1], '48h':[8], '72h':[9], '120h':[10], '168h':[11]};
let qpfLayer = null, qpfWin = '6h';
function makeQpf(win) { return L.esri.dynamicMapLayer({url: QPF, layers: qpfLayers[win], opacity: .6, pane:'rainPane', attribution:'NWS WPC'}); }
// draw 0.2% first so the 1% and floodway sit on top
if (window.FEMA_ZONES) window.FEMA_ZONES.features.sort((a,b)=> (a.properties.zone==='0.2% (500-yr)'?0:a.properties.zone==='Floodway'?2:1) - (b.properties.zone==='0.2% (500-yr)'?0:b.properties.zone==='Floodway'?2:1));
const FEMA_STY = {'Floodway':{color:'#08306b',fillColor:'#08306b',fillOpacity:.40}, '1% (100-yr) Zone AE':{color:'#2171b5',fillColor:'#4292c6',fillOpacity:.30},
  '1% (100-yr) Zone A':{color:'#2171b5',fillColor:'#6baed6',fillOpacity:.30}, '0.2% (500-yr)':{color:'#9ecae1',fillColor:'#c6dbef',fillOpacity:.35}};
const nfhl = L.geoJSON(window.FEMA_ZONES || null, {pane:'floodPane', attribution:'FEMA NFHL (effective)',
  style:f=>Object.assign({weight:.8, opacity:.8}, FEMA_STY[f.properties.zone]||{}),
  onEachFeature:(f,l)=> l.bindTooltip('FEMA ' + f.properties.zone, {sticky:true})});

// radar loop: 50 min back to now in 5-minute frames
const loopOffsets = [50,45,40,35,30,25,20,15,10,5,0];
const loopFrames = loopOffsets.map(m => tile(m ? 'nexrad-n0q-900913-m' + String(m).padStart(2,'0') + 'm' : 'nexrad-n0q-900913', {opacity:0}));
let loopTimer = null, loopIdx = 10, loopOn = false;
function showFrame(i) {
  loopFrames.forEach((l,k)=> l.setOpacity(k===i ? .75 : 0));
  loopIdx = i; $('loopSlider').value = i;
  $('loopLabel').textContent = loopOffsets[i] ? loopOffsets[i] + ' min ago' : 'now';
}
function startLoop() {
  if (!loopOn) { loopFrames.forEach(l=>l.addTo(map)); loopOn = true; }
  $('loopBar').classList.remove('hidden');
  clearInterval(loopTimer); $('loopPlay').textContent = '❚❚';
  loopTimer = setInterval(()=> showFrame((loopIdx+1) % loopFrames.length), 650);
}
function stopLoop(remove) {
  clearInterval(loopTimer); loopTimer = null; $('loopPlay').textContent = '▶';
  if (remove) { loopFrames.forEach(l=>map.removeLayer(l)); loopOn = false; $('loopBar').classList.add('hidden'); }
}
$('loopPlay').onclick = () => loopTimer ? stopLoop(false) : startLoop();
$('loopSlider').oninput = (e) => { stopLoop(false); showFrame(+e.target.value); };

// ------------------------------------------------------------------ scenario (flood) layers
let scen = null;                 // merged view of the river + local scenarios (lists, KPIs, exports)
let scenR = null, scenL = null, valsR = null, valsL = null;
let floodImg = null, floodVals = null;
const floodLayer = L.layerGroup();
const roadLayer = L.layerGroup(), xingLayer = L.layerGroup(), bldgLayer = L.layerGroup();
let floodOpacity = .8;

function depthClass(d) { return d >= 2 ? ['b-hi','Impassable'] : d >= 1 ? ['b-md','Hazardous'] : ['b-lo','Shallow']; }
function roadStyle(f){ const d=f.properties.max_ft; return {color: d>=2?'#d7191c':'#f28e2b', weight: d>=2?6:5, opacity:.95, lineCap:'round'}; }

function loadScenarioScript(id) {
  return new Promise((res, rej) => {
    if (window.SCENARIO_DATA && window.SCENARIO_DATA[id]) return res(window.SCENARIO_DATA[id]);
    const s = document.createElement('script'); s.src = 'data/scenarios/' + id + '.js';
    s.onload = () => res(window.SCENARIO_DATA[id]); s.onerror = () => rej(new Error('missing ' + id));
    document.head.appendChild(s);
  });
}
// ---- view: "critical" (default) shows only the spots that need action; "all" shows everything
const VIEWS = {
  critical: {road:2.0, roadLen:150, mainRoad:1.0, xing:1.0, bldg:3.0, depth:1.0, label:'Critical only'},
  all:      {road:1.0, roadLen:50,  mainRoad:1.0, xing:0.5, bldg:1.5, depth:0.5, label:'Everything'}
};
let view = 'critical';
const TH = () => VIEWS[view];
const roadOK = (p) => (p.max_ft >= TH().road && p.len_ft >= TH().roadLen) || ((p.evac || p.major) && p.max_ft >= TH().mainRoad && p.len_ft >= 50);
const xingOK = (p) => p.overtop_ft >= TH().xing && p.overtop_ft > 0 && !!(p.road && String(p.road).trim()); // only crossings under a mapped road
const bldgOK = (p) => p.max_ft >= TH().bldg;
const FLOOD_BINS = [[0.25,[173,216,240,150]],[0.5,[116,180,230,175]],[1,[49,130,206,195]],[2,[20,90,180,210]],[3,[8,48,140,225]],[5,[60,10,110,235]]];

// recolor the depth grid in the browser so the shaded threshold follows the view
function floodImageURL(sc, vals, mask) {   // mask: grid whose wet pixels hide this layer (river wins)
  if (!vals) return sc.depth_png;
  const c = document.createElement('canvas'); c.width = vals.w; c.height = vals.h;
  const x = c.getContext('2d'), img = x.createImageData(c.width, c.height), d = vals.d, o = img.data, thr = TH().depth;
  for (let i = 0; i < d.length; i += 4) {
    const v = d[i]; if (v === 255) continue; const ft = v * sc.value_scale; if (ft < thr) continue;
    if (mask && mask.d[i] !== 255 && mask.d[i] * sc.value_scale >= thr) continue;
    let col = null; for (const [b, cc] of FLOOD_BINS) if (ft >= b) col = cc;
    if (col) { o[i]=col[0]; o[i+1]=col[1]; o[i+2]=col[2]; o[i+3]=col[3]; }
  }
  x.putImageData(img, 0, 0); return c.toDataURL();
}
function drawScenario() {
  [floodLayer, roadLayer, xingLayer, bldgLayer].forEach(g=>g.clearLayers());
  if (!scen) { updateKPIs(); renderList(); renderLegend(); return; }
  // local storm underneath, river flood on top
  if (scenL) floodLayer.addLayer(L.imageOverlay(floodImageURL(scenL, valsL, (valsR && valsL && valsR.w===valsL.w && valsR.h===valsL.h) ? valsR : null), scenL.bounds, {pane:'floodPane', opacity: floodOpacity, interactive:false}));
  if (scenR) floodLayer.addLayer(floodImg = L.imageOverlay(floodImageURL(scenR, valsR), scenR.bounds, {pane:'floodPane', opacity: floodOpacity, interactive:false}));
  L.geoJSON(scen.roads, {pane:'vecPane', filter:f=>roadOK(f.properties), style: roadStyle, onEachFeature:(f,l)=>{ const p=f.properties, c=depthClass(p.max_ft);
    l.bindPopup(`<div class="pp-t">${esc(p.name)}${p.evac?'<span class="evac">EVAC ROUTE</span>':''}${p.major?'<span class="evac" style="color:#9fd3ff;border-color:#2f5d80">MAJOR ROAD</span>':''}</div><div class="pp-big">${p.max_ft.toFixed(1)} ft</div>${c[1]} · about ${p.len_ft} ft of road under water<div class="pp-m">Owner: ${esc(p.owner||'n/a')}</div>`); }}).addTo(roadLayer);
  L.geoJSON(scen.crossings, {pane:'ptPane', filter:f=> xingOK(f.properties),
    pointToLayer:(f,ll)=>{ const o=f.properties.overtop_ft; return L.circleMarker(ll,{radius:o>0?8:5, weight:2, color:'#111', fillColor:o>1?'#d7191c':o>0?'#f28e2b':'#ffd84d', fillOpacity:1}); },
    onEachFeature:(f,l)=>{ const p=f.properties; l.bindPopup(`<div class="pp-t">${esc(p.kind)} ${esc(p.id)} · ${esc(p.road||'road')}</div>${p.overtop_ft>0?`<div class="pp-big">${p.overtop_ft.toFixed(1)} ft over road</div>`:`<div>Water ${(-p.overtop_ft).toFixed(1)} ft below road</div>`}<div class="pp-m">${esc(p.stream)} · peak water ${p.wse} ft · road ${p.crest} ft (NAVD88)</div>`); }}).addTo(xingLayer);
  L.geoJSON(scen.buildings, {pane:'ptPane', filter:f=>bldgOK(f.properties), pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:view==='critical'?5:3.5,color:'#7f1d1d',weight:1,fillColor:'#fb7185',fillOpacity:.95}),
    onEachFeature:(f,l)=> l.bindPopup(`<div class="pp-t">Building</div>Up to <b>${f.properties.max_ft.toFixed(1)} ft</b> of water next to it<div class="pp-m">Parcel UPI ${esc(f.properties.upi||'n/a')}</div>`)}).addTo(bldgLayer);
  updateKPIs(); renderList(); renderLegend();
}
function decodeVals(sc) {
  return new Promise(res => { const im = new Image(); im.onload = () => { const c=document.createElement('canvas'); c.width=im.width; c.height=im.height; const x=c.getContext('2d'); x.drawImage(im,0,0); res({w:im.width,h:im.height,d:x.getImageData(0,0,im.width,im.height).data}); }; im.onerror = ()=>res(null); im.src = sc.value_png; });
}
function maxVals(a, b) {             // per-pixel max depth of two grids on the same raster
  if (!a || !b || a.w !== b.w || a.h !== b.h) return a || b;
  const d = new Uint8ClampedArray(a.d.length);
  for (let i = 0; i < d.length; i += 4) { const u = a.d[i], v = b.d[i]; d[i] = u === 255 ? v : v === 255 ? u : Math.max(u, v); }
  return {w:a.w, h:a.h, d};
}
function mergeScen(r, l) {
  if (!r || !l) return r || l;
  const byKey = (fa, fb, key, val) => { const m = new Map(); [...fa, ...fb].forEach(f=>{ const k = key(f), o = m.get(k); if (!o || val(f) > val(o)) m.set(k, f); }); return [...m.values()]; };
  return {meta:{id: r.meta.id + '+' + l.meta.id, name: `${r.meta.name} + ${l.meta.name}`, combined:true}, value_scale: r.value_scale,
    stats:{run_complete: r.stats.run_complete && l.stats.run_complete}, bounds: r.bounds,
    roads:{type:'FeatureCollection', features:[...r.roads.features, ...l.roads.features]},
    crossings:{type:'FeatureCollection', features: byKey(r.crossings.features, l.crossings.features, f=>f.properties.id, f=>f.properties.overtop_ft)},
    buildings:{type:'FeatureCollection', features: byKey(r.buildings.features, l.buildings.features, f=>f.properties.upi, f=>f.properties.max_ft)},
    extent:{type:'FeatureCollection', features:[...r.extent.features, ...l.extent.features]}};
}
async function setScenario(idR, idL) {
  const ok = id => { const m = CAT.find(c=>c.id===id); return m && m.available; };
  scenR = ok(idR) ? await loadScenarioScript(idR) : null;
  scenL = ok(idL) ? await loadScenarioScript(idL) : null;
  valsR = scenR ? await decodeVals(scenR) : null; valsL = scenL ? await decodeVals(scenL) : null;
  scen = mergeScen(scenR, scenL); floodVals = maxVals(valsR, valsL);
  drawScenario();
}
function setView(v) {
  view = v;
  document.querySelectorAll('#viewSeg button').forEach(b=> b.classList.toggle('on', b.dataset.view === v));
  $('viewNote').textContent = v === 'critical'
    ? 'Showing only roads with 2 ft+ of water over 150 ft+ (main roads: 1 ft+ over 50 ft+), crossings with 1 ft+ over the road, buildings with 3 ft+ alongside, and flooding 1 ft+ deep.'
    : 'Showing roads with 1 ft+ of water over 50 ft+, crossings with ½ ft+ over the road, buildings with 1½ ft+ alongside, and flooding ½ ft+ deep.';
  drawScenario();
}
function valsAt(v, sc, latlng) {
  const b = sc.bounds, p = L.CRS.EPSG3857.project(latlng), sw = L.CRS.EPSG3857.project(L.latLng(b[0])), ne = L.CRS.EPSG3857.project(L.latLng(b[1]));
  const fx = (p.x - sw.x) / (ne.x - sw.x), fy = (ne.y - p.y) / (ne.y - sw.y);
  if (fx<0||fx>=1||fy<0||fy>=1) return null;
  const x = v.d[(Math.floor(fy*v.h)*v.w + Math.floor(fx*v.w))*4]; return x === 255 ? 0 : x * sc.value_scale;
}
function depthAt(latlng) {
  if (!floodVals || !scen) return null;
  const b = scen.bounds, p = L.CRS.EPSG3857.project(latlng), sw = L.CRS.EPSG3857.project(L.latLng(b[0])), ne = L.CRS.EPSG3857.project(L.latLng(b[1]));
  const fx = (p.x - sw.x) / (ne.x - sw.x), fy = (ne.y - p.y) / (ne.y - sw.y);
  if (fx<0||fx>=1||fy<0||fy>=1) return null;
  const i = (Math.floor(fy*floodVals.h)*floodVals.w + Math.floor(fx*floodVals.w))*4, v = floodVals.d[i];
  return v === 255 ? 0 : v * scen.value_scale;
}
map.on('click', (e) => {
  if (!scen || !map.hasLayer(floodLayer)) return;
  const d = depthAt(e.latlng); if (d == null) return;
  const part = (sc, v) => { if (!sc || !v) return ''; const f = valsAt(v, sc, e.latlng); return f==null ? '' : `<div class="pp-m">${sc===scenR?'River':'Storm'}: ${f.toFixed(1)} ft</div>`; };
  const both = scenR && scenL ? part(scenR, valsR) + part(scenL, valsL) : '';
  const txt = d < .25 ? 'Little or no standing water expected here.' : d < .5 ? 'Shallow water. Passable with care.' : d < 1 ? 'Hazardous: can stall cars and sweep a person off their feet when moving.' : 'Dangerous: do not enter. Can float vehicles.';
  L.popup().setLatLng(e.latlng).setContent(`<div class="pp-m">${esc(scen.meta.name)}</div><div class="pp-big">${d.toFixed(1)} ft</div>${both}${txt}`).openOn(map);
});

// ------------------------------------------------------------------ layer panel
const LAYERS = [
  {group:'Live weather'},
  {id:'radar', name:'Radar (now)', sw:'linear-gradient(90deg,#04e9e7,#02fd02,#fdf802,#fd0000)', add:()=>radarNow.addTo(map), rm:()=>map.removeLayer(radarNow)},
  {id:'loop', name:'Radar loop (last 50 min)', sw:'linear-gradient(90deg,#02fd02,#fd9500,#fd0000)', add:()=>{ if (state.radar) toggle('radar', false); startLoop(); }, rm:()=>stopLoop(true)},
  {id:'past', name:'Rain that has fallen', sw:'linear-gradient(90deg,#9ee39e,#2a9df4,#c20f0f)', choices:['1h','24h','72h'], val:'24h',
    add:(v)=>rainPast[v].addTo(map), rm:()=>Object.values(rainPast).forEach(l=>map.removeLayer(l))},
  {id:'qpf', name:'Forecast rain (NWS)', sw:'linear-gradient(90deg,#7cfc00,#1e90ff,#8a2be2)', choices:['6h','24h','48h','72h','120h','168h'], val:'6h',
    add:(v)=>{ qpfWin=v; qpfLayer=makeQpf(v).addTo(map); }, rm:()=>{ if(qpfLayer){ map.removeLayer(qpfLayer); qpfLayer=null; } }},
  {id:'alerts', name:'NWS warning areas', sw:'#e0393e', on:true, add:()=>alertLayer.addTo(map), rm:()=>map.removeLayer(alertLayer)},
  {group:'Flood model'},
  {id:'flood', name:'Flood depth', sw:'linear-gradient(90deg,#add8f0,#3182ce,#08308c,#3c0a6e)', on:true, opacity:true, add:()=>floodLayer.addTo(map), rm:()=>map.removeLayer(floodLayer)},
  {id:'roads', name:'Flooded roads', sw:'#d7191c', on:true, add:()=>roadLayer.addTo(map), rm:()=>map.removeLayer(roadLayer)},
  {id:'xings', name:'Culverts & bridges at risk', sw:'#f28e2b', on:true, add:()=>xingLayer.addTo(map), rm:()=>map.removeLayer(xingLayer)},
  {id:'bldg', name:'Buildings with water nearby', sw:'#fb7185', add:()=>bldgLayer.addTo(map), rm:()=>map.removeLayer(bldgLayer)},
  {group:'Infrastructure'},
  {id:'allx', name:'All road crossings', sw:'#e2e8f0', add:()=>xingBase.addTo(map), rm:()=>map.removeLayer(xingBase)},
  {id:'pipes', name:'Storm sewers', sw:'#7c3aed', add:()=>pipeLayer.addTo(map), rm:()=>map.removeLayer(pipeLayer)},
  {id:'outf', name:'Storm outfalls', sw:'#c4b5fd', add:()=>outfallLayer.addTo(map), rm:()=>map.removeLayer(outfallLayer)},
  {id:'gauges', name:'Stream gauges (live)', sw:'#10b981', on:true, add:()=>gaugeLayer.addTo(map), rm:()=>map.removeLayer(gaugeLayer)},
  {group:'Reference'},
  {id:'fema', name:'FEMA flood zones', sw:'rgba(0,120,255,.45)', on:true, add:()=>nfhl.addTo(map), rm:()=>map.removeLayer(nfhl)},
  {id:'ws', name:'Watershed boundary', sw:'#0b3d91', on:true, add:()=>wsLayer.addTo(map), rm:()=>map.removeLayer(wsLayer)},
  {id:'streams', name:'Streams', sw:'#2b7bd6', on:true, add:()=>streamLayer.addTo(map), rm:()=>map.removeLayer(streamLayer)},
  {id:'muni', name:'Municipal boundaries', sw:'#6a3d9a', add:()=>muniLayer.addTo(map), rm:()=>map.removeLayer(muniLayer)},
];
const state = {};
const alertLayer = L.geoJSON(null, {pane:'vecPane', style:f=>({color: /warning/i.test(f.properties.event)?'#e0393e':'#d8b100', weight:2, fillOpacity:.08}),
  onEachFeature:(f,l)=> l.bindPopup(`<div class="pp-t">${esc(f.properties.event)}</div><div class="pp-m">${esc(f.properties.headline||'')}</div>`)});
const gaugeLayer = L.layerGroup(); const gaugeMarkers = {};

function toggle(id, on) {
  const d = LAYERS.find(x=>x.id===id); if (!d) return;
  if (on === state[id]) return;
  state[id] = on;
  const cb = document.querySelector(`[data-lyr="${id}"]`); if (cb) cb.checked = on;
  if (on) d.add(d.val); else d.rm();
  if (id==='loop' && on && state.radar) toggle('radar', false);
  if (id==='radar' && on && state.loop) toggle('loop', false);
  renderLegend();
}
function buildPanel() {
  const body = $('layerBody'); body.innerHTML = '';
  const bm = document.createElement('div'); bm.className='lgroup';
  bm.innerHTML = '<div class="lgroup-t">Base map</div><div class="radio-row">' + Object.keys(basemaps).map(k=>`<button data-bm="${k}" class="${k===curBase?'on':''}">${k}</button>`).join('') + '</div>';
  body.appendChild(bm);
  bm.querySelectorAll('[data-bm]').forEach(b=> b.onclick = () => { map.removeLayer(basemaps[curBase]); curBase=b.dataset.bm; basemaps[curBase].addTo(map); bm.querySelectorAll('[data-bm]').forEach(x=>x.classList.toggle('on', x===b)); });
  let grp = null;
  LAYERS.forEach(d => {
    if (d.group) { grp = document.createElement('div'); grp.className='lgroup'; grp.innerHTML = `<div class="lgroup-t">${d.group}</div>`; body.appendChild(grp); return; }
    const row = document.createElement('label'); row.className='lyr';
    row.innerHTML = `<input type="checkbox" data-lyr="${d.id}"><span class="sw" style="background:${d.sw}"></span><span>${d.name}</span>`;
    grp.appendChild(row);
    row.querySelector('input').onchange = (e)=> toggle(d.id, e.target.checked);
    if (d.choices) {
      const rr = document.createElement('div'); rr.className='radio-row'; rr.style.marginLeft='22px';
      rr.innerHTML = d.choices.map(c=>`<button data-c="${c}" class="${c===d.val?'on':''}">${WIN_LABEL[c]}</button>`).join('');
      rr.querySelectorAll('button').forEach(b=> b.onclick = (ev)=>{ ev.preventDefault(); d.val=b.dataset.c; rr.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b)); if (state[d.id]) { d.rm(); d.add(d.val); } else toggle(d.id,true); renderLegend(); });
      grp.appendChild(rr);
    }
    if (d.opacity) {
      const op = document.createElement('div'); op.className='op';
      op.innerHTML = `<span>see-through</span><input type="range" min="20" max="100" value="${floodOpacity*100}">`;
      op.querySelector('input').oninput = (e)=>{ floodOpacity = e.target.value/100; floodLayer.eachLayer(l=>l.setOpacity && l.setOpacity(floodOpacity)); };
      grp.appendChild(op);
    }
  });
  LAYERS.forEach(d=> { if (d.on) toggle(d.id, true); });
}
$('lpToggle').onclick = () => { const h = $('layerBody').classList.toggle('hidden'); $('lpToggle').textContent = h ? '+' : '–'; };
$('sideToggle').onclick = () => { $('side').classList.toggle('collapsed'); setTimeout(()=>map.invalidateSize(), 50); };

// ------------------------------------------------------------------ legend
function renderLegend() {
  const parts = [];
  if (state.flood && scen) parts.push(`<div class="lg"><div class="lg-t">Flood depth (${esc(scen.meta.name)})</div>${scenR && scenL ? '<div class="lg-n">River flood drawn on top of the local storm. Overlaying two runs approximates a combined event; it does not model how they interact.</div>' : ''}
    ${[['#add8f0','¼ – ½ ft',.25],['#74b4e6','½ – 1 ft',.5],['#3182ce','1 – 2 ft',1],['#145ab4','2 – 3 ft',2],['#08308c','3 – 5 ft',3],['#3c0a6e','over 5 ft',5]].filter(r=>r[2]>=TH().depth).map(r=>`<div class="lg-r"><i style="background:${r[0]}"></i>${r[1]}</div>`).join('')}
    <div class="lg-n">Click the map to read the depth at a spot.</div></div>`);
  if ((state.roads || state.xings) && scen) parts.push(`<div class="lg"><div class="lg-t">Roads &amp; crossings</div>
    <div class="lg-r"><i style="background:#d7191c"></i>Road: 2 ft+ (impassable)</div><div class="lg-r"><i style="background:#f28e2b"></i>Road: 1 – 2 ft (hazardous)</div>
    <div class="lg-r"><i style="background:#d7191c;border-radius:50%"></i>Crossing: 1 ft+ over road</div><div class="lg-r"><i style="background:#f28e2b;border-radius:50%"></i>Crossing: water over road</div><div class="lg-r"><i style="background:#ffd84d;border-radius:50%"></i>Crossing: below road</div></div>`);
  if (state.radar || state.loop) parts.push(`<div class="lg"><div class="lg-t">Radar (rain rate, rough)</div>
    ${[['#04e9e7','Trace'],['#02b902','~0.1 in/hr'],['#008e00','~0.25 in/hr'],['#fdf802','~0.5 in/hr'],['#fd9500','~1.25 in/hr'],['#fd0000','~2.5 in/hr'],['#bc0000','~4 in/hr'],['#f800fd','8+ in/hr']].map(r=>`<div class="lg-r"><i style="background:${r[0]}"></i>${r[1]}</div>`).join('')}
    <div class="lg-n">Radar shows reflectivity, not measured rain. Rates are rough. Faint gray-purple squares are very weak returns (clear air, birds, drizzle), not real rain.</div></div>`);
  if (state.qpf) parts.push(`<div class="lg"><div class="lg-t">Forecast rain, next ${WIN_LABEL[qpfWin]}</div>
    ${[['#7fff00','0.01"'],['#00ff00','0.10"'],['#008b00','0.25"'],['#104e8b','0.50"'],['#1e90ff','0.75"'],['#00b2ee','1.00"'],['#00eeee','1.25"'],['#8968cd','1.50"'],['#912cee','1.75"'],['#8b008b','2.00"'],['#8b0000','2.50"'],['#ff0000','3.00"+']].map(r=>`<div class="lg-r"><i style="background:${r[0]}"></i>${r[1]}</div>`).join('')}
    <div class="lg-n">NWS WPC forecast, averaged over ~20 km squares.</div></div>`);
  if (state.past) parts.push(`<div class="lg"><div class="lg-t">Rain that has fallen</div><div class="lg-n">NOAA MRMS radar + gauge estimate. Greens are light totals, blues moderate, reds and purples heavy. Exact totals for the watershed are in the side panel.</div></div>`);
  if (state.fema) parts.push(`<div class="lg"><div class="lg-t">FEMA flood zones</div><div class="lg-n"><span style="color:#08306b">■</span> Regulatory floodway · <span style="color:#4292c6">■</span> 1% (100-yr) floodplain · <span style="color:#9ecae1">■</span> 0.2% (500-yr). From FEMA's effective NFHL. Hover for the zone.</div></div>`);
  if (state.gauges) parts.push(`<div class="lg"><div class="lg-t">Stream gauges</div>
    <div class="lg-r"><i style="background:#10b981;border-radius:50%"></i>Normal / no flood stage set</div><div class="lg-r"><i style="background:#d8b100;border-radius:50%"></i>Action stage</div><div class="lg-r"><i style="background:#f08a24;border-radius:50%"></i>Minor flooding</div><div class="lg-r"><i style="background:#e0393e;border-radius:50%"></i>Moderate / major</div></div>`);
  const lg = $('legend');
  lg.innerHTML = parts.length ? `<div class="lg-head"><span>Legend</span><button class="ghost small" id="lgToggle">${legendMin?'+':'–'}</button></div><div class="lg-body${legendMin?' hidden':''}">${parts.join('')}</div>` : '';
  const t = $('lgToggle'); if (t) t.onclick = () => { legendMin = !legendMin; renderLegend(); };
}
let legendMin = true;   // legend starts collapsed

// ------------------------------------------------------------------ live data: rain
const live = {qpf:{}, past:{}, alerts:[]};
async function loadPastRain() {
  const end = new Date(), start = new Date(end - 7*864e5);
  const d = (x)=> x.toISOString().slice(0,10);
  try {
    const j = await getJSON(`https://mesonet.agron.iastate.edu/iemre/multiday/${d(start)}/${d(end)}/${CENTER[0].toFixed(3)}/${CENTER[1].toFixed(3)}/json`);
    const v = j.data.map(r=> r.mrms_precip_in).filter(x=>x!=null);
    const sum = (n)=> v.slice(-n).reduce((a,b)=>a+b,0);
    live.past = {d1: sum(1), d3: sum(3), d7: sum(7)};
    $('past1').querySelector('.v').textContent = fmtIn(live.past.d1);
    $('past3').querySelector('.v').textContent = fmtIn(live.past.d3);
    $('past7').querySelector('.v').textContent = fmtIn(live.past.d7);
  } catch (e) { ['past1','past3','past7'].forEach(id=> $(id).querySelector('.v').textContent='n/a'); }
}
async function qpfAt(layerId) {
  const q = new URLSearchParams({geometry:`${CENTER[1]},${CENTER[0]}`, geometryType:'esriGeometryPoint', inSR:'4326', spatialRel:'esriSpatialRelIntersects', outFields:'qpf,start_time,end_time,issue_time', returnGeometry:'false', f:'json'});
  const j = await getJSON(`${QPF}/${layerId}/query?${q}`);
  const f = (j.features||[]).map(x=>x.attributes);
  if (!f.length) return {v:0, meta:null};
  const best = f.reduce((a,b)=> (b.qpf > a.qpf ? b : a));
  return {v: best.qpf, meta: best};
}
async function loadQpf() {
  const wins = [['6h',7,'6-hr','qpf6'], ['24h',1,'24-hr','qpf24'], ['72h',9,'3-day','qpf72'], ['120h',10,'5-day','qpf120'], ['168h',11,'7-day','qpf168']];
  await Promise.all(wins.map(async ([k, lid, dur, el]) => {
    try {
      const r = await qpfAt(lid); live.qpf[k] = r.v;
      const rp = returnPeriod(r.v, dur); live.qpf[k+'_rp'] = rp ? rp.rp : 0;
      $(el).querySelector('.v').textContent = fmtIn(r.v);
      $(el).querySelector('.rp').textContent = r.v >= .05 && rp ? rp.label : '';
      if (k==='6h' && r.meta) $('qpfIssued').textContent = `Forecast issued ${r.meta.issue_time || ''} UTC.`;
    } catch (e) { live.qpf[k] = null; $(el).querySelector('.v').textContent = 'n/a'; }
  }));
}
async function loadAlerts() {
  try {
    const j = await getJSON(`https://api.weather.gov/alerts/active?point=${CENTER[0].toFixed(4)},${CENTER[1].toFixed(4)}`, {headers:{'Accept':'application/geo+json'}});
    live.alerts = (j.features||[]);
    alertLayer.clearLayers(); live.alerts.filter(f=>f.geometry).forEach(f=> alertLayer.addData(f));
  } catch (e) { live.alerts = null; }
  renderAlerts();
}
function renderAlerts() {
  const box = $('alerts');
  if (live.alerts == null) { box.innerHTML = '<div class="fine">Could not reach NWS alerts.</div>'; return; }
  box.innerHTML = live.alerts.map(f=>{ const p=f.properties, warn=/warning/i.test(p.event);
    const until = p.ends || p.expires; return `<div class="alert ${warn?'':'minor'}"><b>${esc(p.event)}</b><span class="when">${until?'until '+new Date(until).toLocaleString([], {weekday:'short',hour:'numeric',minute:'2-digit'}):''}</span><div>${esc(p.headline||'')}</div></div>`; }).join('');
}

// ------------------------------------------------------------------ status level
function computeStatus() {
  const al = live.alerts || [];
  const ff = al.filter(f=>FLOOD_EVENTS.test(f.properties.event));
  const warn = ff.some(f=>/warning/i.test(f.properties.event)), watch = ff.some(f=>/watch|advisory|statement/i.test(f.properties.event));
  const rp = Math.max(live.qpf['6h_rp']||0, live.qpf['24h_rp']||0, live.qpf['72h_rp']||0);
  const q6 = live.qpf['6h']||0, q24 = live.qpf['24h']||0;
  let lvl='low', title='No flooding expected', why=[];
  if (q6 >= .5 || q24 >= 1) { lvl='watch'; title='Heavy rain in the forecast'; }
  if (watch || rp >= 2) { lvl='elev'; title='Flooding possible'; }
  if (warn || rp >= 10) { lvl='high'; title='Flooding likely'; }
  if (ff.length) why.push(ff.map(f=>f.properties.event).join(', ') + ' in effect.');
  if (rp >= 1) { const w = (live.qpf['6h_rp']||0) >= rp ? 'next 6 hr' : (live.qpf['24h_rp']||0) >= rp ? 'next 24 hr' : 'next 3 days';
    why.push(`Forecast rain over the ${w} is about a ${niceRP(rp)}-year storm.`); }
  else if (['6h','24h','72h'].every(k=> live.qpf[k] == null)) why.push('NWS rain forecast unavailable right now.');
  else why.push(q24 > 0 ? `Up to ${q24.toFixed(2)}" forecast in the next 24 hr, below a 1-year storm.` : 'No significant rain in the NWS forecast.');
  const el = $('level'); el.className = 'level ' + lvl; el.textContent = {low:'LOW',watch:'WATCH',elev:'ELEVATED',high:'HIGH'}[lvl];
  $('levelTitle').textContent = title; $('levelWhy').textContent = why.join(' ');
  return rp;
}

// ------------------------------------------------------------------ forecast → scenario matching
// River forecast points (NWS NWPS). Flows are converted with ratings fitted to USGS peak records.
const RIVER_PTS = {};   // no NWS river forecast points inside the Valley Creek watershed
live.river = {};
async function loadRiverForecasts() {
  await Promise.all(Object.keys(RIVER_PTS).map(async lid => {
    const o = {lid}; try {
      const g = await getJSON(`https://api.water.noaa.gov/nwps/v1/gauges/${lid}`);
      o.cats = g.flood && g.flood.categories; o.lat = g.latitude; o.lon = g.longitude; o.name = g.name; o.obs = g.status && g.status.observed; o.fc = g.status && g.status.forecast;
      try { const sf = await getJSON(`https://api.water.noaa.gov/nwps/v1/gauges/${lid}/stageflow`);
        const fs = (sf.forecast && sf.forecast.data) || []; const ob = (sf.observed && sf.observed.data) || [];
        const mx = (arr, k) => arr.reduce((m, d) => (d[k] != null && d[k] > -900 && d[k] > m) ? d[k] : m, -Infinity);
        o.fcPeakStage = fs.length ? mx(fs,'primary') : null; o.fcPeakFlow = fs.length ? mx(fs,'secondary') : null; // kcfs
        o.fcUnits = sf.forecast && sf.forecast.secondaryUnits; o.obsFlow = ob.length ? ob[ob.length-1].secondary : null;
        o.fcPeakTime = (fs.find(d=>d.primary===o.fcPeakStage)||{}).validTime; o.issued = sf.forecast && sf.forecast.issuedTime;
      } catch (e) {}
      const rat = M.gauges && M.gauges[RIVER_PTS[lid].usgs];
      if (o.fcPeakFlow == null && o.fcPeakStage != null && rat) o.fcPeakFlowCfs = rat.a * Math.pow(Math.max(o.fcPeakStage - rat.h0, 0), rat.b);
      else if (o.fcPeakFlow != null) o.fcPeakFlowCfs = /kcfs/i.test(o.fcUnits||'kcfs') ? o.fcPeakFlow*1000 : o.fcPeakFlow;
    } catch (e) { o.err = true; }
    live.river[lid] = o;
  }));
  renderRiver();
}
function renderRiver() {
  const box = $('riverBox'); if (!box) return;
  box.innerHTML = Object.entries(RIVER_PTS).map(([lid,p])=>{ const o = live.river[lid] || {};
    const cat = (o.fc && o.fc.floodCategory) || '', ocat = (o.obs && o.obs.floodCategory) || '';
    const st = o.obs && o.obs.primary != null ? o.obs.primary.toFixed(1)+' ft now' : 'no data';
    const pk = o.fcPeakStage != null && isFinite(o.fcPeakStage) ? `forecast crest ${o.fcPeakStage.toFixed(1)} ft${o.fcPeakTime?' '+new Date(o.fcPeakTime).toLocaleString([], {weekday:'short',hour:'numeric'}):''}${o.fcPeakFlowCfs?' (~'+Math.round(o.fcPeakFlowCfs/100)/10+'k cfs)':''}` : 'no forecast';
    const flood = o.cats ? `flood stage ${o.cats.minor && o.cats.minor.stage} ft` : '';
    const sev = /major|moderate/i.test(cat) ? 'b-hi' : /minor/i.test(cat) ? 'b-md' : /action/i.test(cat) ? 'b-lo' : 'b-ok';
    return `<div class="item" data-lid="${lid}" title="Show on map"><div><div class="nm">${esc(p.name)} <span class="fine">(${lid})</span></div><div class="meta">${st} · ${pk} · ${flood}</div></div><span class="badge ${sev}">${esc(((cat||ocat||'—')+'').replace(/_/g,' ').replace(/^no flooding$/i,'Normal').replace(/^\w/,c=>c.toUpperCase()))}</span></div>`; }).join('');
  box.querySelectorAll('[data-lid]').forEach(el=> el.onclick = ()=> showRiverGauge(el.dataset.lid));
}
window.__upPop = () => { const p = map._popup; if (p && p.isOpen()) { p.update(); p._adjustPan && p._adjustPan(); } };
const catTxt = c => ((c||'')+'').replace(/_/g,' ').replace(/^no flooding$/i,'normal');
const nwpsLinks = lid => `<a href="https://water.noaa.gov/gauges/${lid.toLowerCase()}" target="_blank" rel="noopener">NOAA gauge viewer ↗</a>`;
const nwpsHydro = lid => `<a href="https://water.noaa.gov/gauges/${lid.toLowerCase()}" target="_blank" rel="noopener"><img class="hydro" src="https://water.noaa.gov/resources/hydrographs/${lid.toLowerCase()}_hg.png?t=${Math.floor(Date.now()/9e5)}" alt="NWS observed and forecast hydrograph" style="width:100%;max-width:340px;display:block;margin:6px 0;border-radius:4px;background:#fff" onload="window.__upPop&&window.__upPop()" onerror="this.parentNode.style.display='none'"></a>`;
function riverForecastLine(lid) {
  const o = (live.river||{})[lid]; if (!o || o.fcPeakStage == null || !isFinite(o.fcPeakStage)) return '<div class="pp-m">No NWS forecast issued for this gauge right now.</div>';
  return `<div class="pp-m">NWS forecast crest <b>${o.fcPeakStage.toFixed(1)} ft</b>${o.fcPeakTime?' '+new Date(o.fcPeakTime).toLocaleString([], {weekday:'short',hour:'numeric'}):''}${o.fcPeakFlowCfs?' (~'+Math.round(o.fcPeakFlowCfs/100)/10+'k cfs)':''}${o.cats&&o.cats.minor?' · flood stage '+o.cats.minor.stage+' ft':''}</div>`;
}
function showRiverGauge(lid) {
  const p = RIVER_PTS[lid], o = (live.river||{})[lid] || {};
  const g = gauges['USGS-' + p.usgs];
  const lat = g ? g.lat : o.lat, lon = g ? g.lon : o.lon; if (lat == null) return;
  if (!state.gauges) toggle('gauges', true);
  map.setView([lat, lon], Math.max(map.getZoom(), 14));
  const mk = gaugeMarkers[g ? g.id : ''];
  if (mk) mk.openPopup();
  else L.popup({maxWidth:360, minWidth:260}).setLatLng([lat,lon]).setContent(`<div class="pp-t">${esc(o.name||p.name)}</div>${riverForecastLine(lid)}${nwpsHydro(lid)}${nwpsLinks(lid)} · <a href="https://waterdata.usgs.gov/monitoring-location/${p.usgs}/" target="_blank" rel="noopener">USGS page ↗</a>`).openOn(map);
}
function matchScenario() {
  const rv = live.river || {}; const qS = rv.PTNP1 && rv.PTNP1.fcPeakFlowCfs, qP = rv.GRAP1 && rv.GRAP1.fcPeakFlowCfs;
  const notes = []; let river = null, local = null;
  if (!Object.keys(RIVER_PTS).length) { /* rain-driven watershed: no river layer */ }
  else if (qS == null && qP == null) notes.push('NWS river forecasts could not be reached.');
  else {
    const wantS = (qS||0)*1.02, wantP = (qP||0);
    notes.push(`NWS forecast crest: Schuylkill ~${Math.round(wantS/100)/10}k cfs, Perkiomen ~${Math.round(wantP/100)/10}k cfs.`);
    if (wantS < 12000 && wantP < 6000) notes.push('Rivers are forecast to stay within their banks.');
    else {
      const ladder = CAT.filter(c=>c.kind==='river' && (c.rp!=null || c.id==='riv_q12k')).sort((a,b)=>a.qS-b.qS);
      const want = ladder.find(c=> c.qS >= wantS && c.qP >= wantP) || ladder[ladder.length-1];
      river = want.available ? want : (ladder.filter(c=>c.available && c.qS>=want.qS)[0] || ladder.filter(c=>c.available).pop());
      if (river) notes.push(`River layer: <b>${esc(river.name)}</b> (closest modeled level at or above the forecast).`);
    }
  }
  const r6 = live.qpf['6h_rp']||0, r24 = live.qpf['24h_rp']||0, rrp = Math.max(r6, r24);
  if (['6h','24h','72h'].every(k=> live.qpf[k] == null)) notes.push('NWS rain forecast unavailable.');
  else if (rrp >= 2) {
    const fam = r6 >= r24 ? '6-hr' : '24-hr';
    const rain = CAT.filter(c=>c.available && c.kind==='rain');
    let cand = rain.filter(c=>c.duration===fam); if (!cand.length) cand = rain;
    local = cand.sort((a,b)=> Math.abs(Math.log(a.rp/rrp)) - Math.abs(Math.log(b.rp/rrp)))[0] || null;
    if (local) notes.push(`Forecast rain is about a ${niceRP(rrp)}-year storm. Storm layer: <b>${esc(local.name)}</b>.`);
  } else notes.push('Forecast rain is below a 2-year storm.');
  if (!river && !local) notes.push('No flooding layer is shown. Pick one from the lists to explore.');
  return {river, local, note: notes.join(' ')};
}
function fillScenarioSelect() {
  const opt = c => `<option value="${c.id}" ${c.available?'':'disabled'}>${esc(c.name)}${c.available?'':'  (not modeled yet)'}</option>`;
  $('scenarioSel').innerHTML = '<option value="">— no river flood —</option>' + CAT.filter(c=>c.kind==='river' || c.kind==='combo').map(opt).join('');
  const hr = c => c.duration_hr || parseFloat(c.duration) || 0;
  $('localSel').innerHTML = '<option value="">— no storm —</option>' + CAT.filter(c=>c.kind==='rain' || c.kind==='test').sort((a,b)=>(a.kind==='test')-(b.kind==='test') || hr(a)-hr(b) || a.rp-b.rp).map(opt).join('');
  if (CAT.some(c=>c.kind==='river' || c.kind==='combo')) $('riverPick').style.display = '';
}
async function applyScenarioChoice() {
  let note;
  if ($('autoMatch').checked) { const m = matchScenario(); $('scenarioSel').value = m.river ? m.river.id : ''; $('localSel').value = m.local ? m.local.id : ''; note = m.note; }
  else { const n = [$('scenarioSel').value, $('localSel').value].map(id=>CAT.find(x=>x.id===id)).filter(Boolean).map(c=>esc(c.name));
    note = n.length ? `Showing <b>${n.join('</b> with <b>')}</b>${n.length>1?' (river layer on top)':''}.` : 'No flood layer selected.'; }
  const comboPicked = (CAT.find(c=>c.id===$('scenarioSel').value)||{}).kind === 'combo';
  if (comboPicked && $('localSel').value) { note += ' <span class="warn">The combined run already includes rain, so the local storm layer is ignored.</span>'; }
  await setScenario($('scenarioSel').value, comboPicked ? '' : $('localSel').value);
  if (scen && scen.stats.run_complete === false) note += '<br><span class="warn">One of these model runs did not finish. Results are partial.</span>';
  $('scenNote').innerHTML = note;
  renderLegend();
}
$('autoMatch').onchange = applyScenarioChoice;
document.querySelectorAll('#viewSeg button').forEach(b=> b.onclick = ()=> setView(b.dataset.view));
$('scenarioSel').onchange = $('localSel').onchange = () => { $('autoMatch').checked = false; applyScenarioChoice(); };

// ------------------------------------------------------------------ KPIs + lists
function updateKPIs() {
  const s = scen && scen.stats;
  if (!s) { ['kRoads','kX','kB','kA'].forEach(k=>$(k).textContent='–'); return; }
  const roads = scen.roads.features.filter(f=>roadOK(f.properties));
  $('kRoads').textContent = new Set(roads.map(f=>f.properties.name)).size;
  $('kX').textContent = scen.crossings.features.filter(f=>xingOK(f.properties)).length;
  $('kB').textContent = scen.buildings.features.filter(f=>bldgOK(f.properties)).length;
  { let n = 0; if (floodVals) { const d = floodVals.d, thr = TH().depth / scen.value_scale; for (let i=0;i<d.length;i+=4) if (d[i] !== 255 && d[i] >= thr) n++; }
    if (floodVals) {
      const bb = scen.bounds, sw = L.CRS.EPSG3857.project(L.latLng(bb[0])), ne = L.CRS.EPSG3857.project(L.latLng(bb[1]));
      const px = ((ne.x-sw.x)/floodVals.w) * ((ne.y-sw.y)/floodVals.h) * Math.pow(Math.cos(bb[0][0]*Math.PI/180),2) * 10.7639; // sq ft per pixel
      $('kA').textContent = Math.round(n * px / 43560);
    } else $('kA').textContent = '–'; }
  const t = TH();
  const fmt = v => v===0.5?'½':v===1.5?'1½':String(v);
  $('kRoadsT').textContent = `roads with ${fmt(t.road)} ft+ of water (main roads ${fmt(t.mainRoad)} ft+)`;
  $('kXT').textContent = `culverts / bridges with ${fmt(t.xing)} ft+ over the road`;
  $('kBT').textContent = `buildings with ${fmt(t.bldg)} ft+ water alongside`;
  $('kAT').textContent = `acres under ${t.depth>=1?'1':'½'} ft+ of water`;
}
let curTab = 'roads';
document.querySelectorAll('#tabs button').forEach(b=> b.onclick = ()=> setTab(b.dataset.tab));
document.querySelectorAll('.kpi[data-tab]').forEach(k=> k.onclick = ()=> setTab(k.dataset.tab));
function setTab(t) { curTab = t; document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on', b.dataset.tab===t)); renderList(); }
function zoomTo(geom) {
  const l = L.geoJSON(geom); const b = l.getBounds();
  if (geom.type === 'Point') map.setView(b.getCenter(), 17); else map.fitBounds(b, {maxZoom:17, padding:[60,60]});
}
function renderList() {
  const box = $('list');
  if (curTab === 'gauges') return renderGaugeList();
  if (!scen) { box.innerHTML = '<div class="fine">No flood scenario loaded.</div>'; return; }
  let rows = [];
  if (curTab === 'roads') {
    // group segments by road name
    const g = {};
    scen.roads.features.filter(f=>roadOK(f.properties)).forEach(f=>{ const p=f.properties; const k=p.name; (g[k] = g[k] || {name:k, max:0, len:0, n:0, evac:false, major:false, feats:[]}); g[k].major = g[k].major || p.major; g[k].max=Math.max(g[k].max,p.max_ft); g[k].len+=p.len_ft; g[k].n++; g[k].evac = g[k].evac || p.evac; g[k].feats.push(f); });
    rows = Object.values(g).sort((a,b)=> (b.evac-a.evac) || (b.major-a.major) || (b.max-a.max)).map(r=>{ const c=depthClass(r.max); return {html:`<div><div class="nm">${esc(r.name)}${r.evac?'<span class="evac">EVAC</span>':''}${r.major?'<span class="evac" style="color:#9fd3ff;border-color:#2f5d80">MAJOR</span>':''}</div><div class="meta">${r.n} spot${r.n>1?'s':''} · ~${r.len} ft under water · ${c[1]}</div></div><span class="badge ${c[0]}">${r.max.toFixed(1)} ft</span>`, geom:{type:'GeometryCollection', geometries:r.feats.map(f=>f.geometry)}}; });
  } else if (curTab === 'crossings') {
    rows = scen.crossings.features.filter(f=> xingOK(f.properties)).sort((a,b)=>b.properties.overtop_ft-a.properties.overtop_ft).map(f=>{ const p=f.properties, o=p.overtop_ft;
      const b = o>1?['b-hi',`${o.toFixed(1)} ft over`]:o>0?['b-md',`${o.toFixed(1)} ft over`]:['b-ok',`${(-o).toFixed(1)} ft below`];
      return {html:`<div><div class="nm">${esc(p.road||'Road')} at ${esc(p.stream||'stream')}</div><div class="meta">${esc(p.kind)} ${esc(p.id)}</div></div><span class="badge ${b[0]}">${b[1]}</span>`, geom:f.geometry}; });
  } else if (curTab === 'buildings') {
    rows = scen.buildings.features.filter(f=>bldgOK(f.properties)).sort((a,b)=>b.properties.max_ft-a.properties.max_ft).slice(0,300).map(f=>{ const p=f.properties, c=depthClass(p.max_ft);
      return {html:`<div><div class="nm">Parcel ${esc(p.upi||'n/a')}</div><div class="meta">water alongside building</div></div><span class="badge ${c[0]}">${p.max_ft.toFixed(1)} ft</span>`, geom:f.geometry}; });
    { const nb = scen.buildings.features.filter(f=>bldgOK(f.properties)).length; if (nb > 300) rows.push({html:`<div class="fine">Showing deepest 300 of ${nb}.</div>`}); }
  }
  box.innerHTML = rows.length ? '' : '<div class="fine">None for this storm.</div>';
  rows.forEach(r=>{ const d=document.createElement('div'); d.className='item'; d.innerHTML=r.html; if (r.geom) d.onclick=()=>zoomTo(r.geom); box.appendChild(d); });
}

// ------------------------------------------------------------------ gauges (USGS + NWS NWPS)
const gauges = {};   // id -> {name, lat, lon, stage, flow, time, nws}
const catColor = {action:'#d8b100', minor:'#f08a24', moderate:'#e0393e', major:'#9b111e'};
async function loadGauges() {
  const [x0,y0,x1,y1] = GAUGE_BBOX;
  try {
    const [lc, ml] = await Promise.all([
      getJSON(`${USGS}latest-continuous/items?f=json&bbox=${x0},${y0},${x1},${y1}&parameter_code=00065,00060&limit=500`),
      getJSON(`${USGS}monitoring-locations/items?f=json&bbox=${x0},${y0},${x1},${y1}&site_type_code=ST&limit=500&properties=monitoring_location_name`).catch(()=>({features:[]}))
    ]);
    const names = {}; (ml.features||[]).forEach(f=> names[f.id] = f.properties.monitoring_location_name);
    const fresh = Date.now() - 3*864e5;
    (lc.features||[]).forEach(f=>{ const p=f.properties; if (!p.time || new Date(p.time) < fresh) return;
      const id = p.monitoring_location_id; const g = gauges[id] = gauges[id] || {id, name: names[id] || id, lon:f.geometry.coordinates[0], lat:f.geometry.coordinates[1], src:'USGS'};
      if (p.parameter_code==='00065') g.stage = +p.value; else g.flow = +p.value; g.time = p.time; });
  } catch (e) { /* USGS unavailable */ }
  try {
    const j = await getJSON(`https://api.water.noaa.gov/nwps/v1/gauges?bbox.xmin=${x0}&bbox.ymin=${y0}&bbox.xmax=${x1}&bbox.ymax=${y1}&srid=EPSG_4326`);
    (j.gauges||[]).forEach(n=>{ const usgsId = n.usgsId ? 'USGS-' + n.usgsId : null; const g = (usgsId && gauges[usgsId]) || (gauges['NWS-'+n.lid] = gauges['NWS-'+n.lid] || {id:'NWS-'+n.lid, name:n.name, lat:n.latitude, lon:n.longitude, src:'NWS'});
      g.nws = {lid:n.lid, cat:(n.status&&n.status.observed&&n.status.observed.floodCategory)||'', fcat:(n.status&&n.status.forecast&&n.status.forecast.floodCategory)||'', obs:n.status&&n.status.observed&&n.status.observed.primary, units:n.status&&n.status.observed&&n.status.observed.primaryUnit}; if (!g.name || g.name.startsWith('USGS-')) g.name = n.name; });
  } catch (e) { /* NWPS unavailable */ }
  // one marker per site: fold NWS-only entries into the nearest USGS gauge (within 1 km) and drop the rest
  Object.values(gauges).filter(g=>g.src==='NWS').forEach(n=>{
    let best=null, bd=1000;
    Object.values(gauges).filter(g=>g.src==='USGS').forEach(u=>{ const d=map.distance([n.lat,n.lon],[u.lat,u.lon]); if (d<bd) { bd=d; best=u; } });
    if (best && !best.nws) best.nws = n.nws;
    delete gauges[n.id];
  });
  drawGauges(); if (curTab==='gauges') renderGaugeList();
}
// where is a gauge relative to the modeled watershed?
const OUTLET = [39.9684, -75.6664];
const wsRings = (()=>{ const g = M.watershed.features[0].geometry; return g.type==='Polygon' ? [g.coordinates[0]] : g.coordinates.map(p=>p[0]); })();
function inWs(lat, lon) { return wsRings.some(r=>{ let c=false; for (let i=0,j=r.length-1;i<r.length;j=i++) { const [xi,yi]=r[i],[xj,yj]=r[j]; if (((yi>lat)!==(yj>lat)) && (lon < (xj-xi)*(lat-yi)/(yj-yi)+xi)) c=!c; } return c; }); }
function gaugeWhere(g) {
  if (inWs(g.lat, g.lon)) return 'In watershed';
  if (map.distance([g.lat,g.lon], OUTLET) < 2500) return 'Just downstream of watershed';
  return 'Outside watershed';
}
function gaugeColor(g) { const c = g.nws && (g.nws.cat||'').toLowerCase(); return catColor[c] || '#10b981'; }
function drawGauges() {
  gaugeLayer.clearLayers(); Object.keys(gaugeMarkers).forEach(k=>delete gaugeMarkers[k]);
  Object.values(gauges).forEach(g=>{
    const m = L.circleMarker([g.lat,g.lon], {pane:'ptPane', radius:7, weight:2, color:'#0b3b2c', fillColor:gaugeColor(g), fillOpacity:1});
    gaugeMarkers[g.id] = m; m.bindPopup(()=> gaugePopup(g), {minWidth:260, maxWidth:360}); m.on('popupopen', ()=> loadSpark(g, m)); m.addTo(gaugeLayer);
  });
}
function gaugePopup(g) {
  const nws = g.nws ? `<div class="pp-m">NWS ${esc(g.nws.lid)} · observed: ${esc(catTxt(g.nws.cat)||'no flood category')}${g.nws.fcat?' · forecast: '+esc(catTxt(g.nws.fcat)):''}</div>` : '';
  const lid = g.nws && g.nws.lid;
  const noaa = lid ? `${RIVER_PTS[lid] ? riverForecastLine(lid) : ''}${nwpsHydro(lid)}` : '';
  return `<div class="pp-t">${esc(g.name)}</div><div class="pp-m">${gaugeWhere(g)}</div>${g.stage!=null?`<div class="pp-big">${g.stage.toFixed(2)} ft</div>`:''}${g.flow!=null?`<div>${Math.round(g.flow)} cfs</div>`:''}${g.time?`<div class="pp-m">${new Date(g.time).toLocaleString()}</div>`:''}${nws}<div id="spark-${g.id.replace(/\W/g,'')}" class="pp-m">${g.src==='USGS'?'Loading last 2 days…':''}</div>${noaa}<div>${g.src==='USGS'?`<a href="https://waterdata.usgs.gov/monitoring-location/${g.id.replace('USGS-','')}/" target="_blank" rel="noopener">USGS page ↗</a>`:''}${lid?(g.src==='USGS'?' · ':'')+nwpsLinks(lid):''}</div>`;
}
async function loadSpark(g) {
  if (g.src !== 'USGS') return;
  const el = () => document.getElementById('spark-' + g.id.replace(/\W/g,''));
  try {
    const pc = g.stage != null ? '00065' : '00060';
    const j = await getJSON(`${USGS}continuous/items?f=json&monitoring_location_id=${g.id}&parameter_code=${pc}&time=P2D&limit=1000&skipGeometry=true&properties=time,value`);
    const pts = (j.features||[]).map(f=>[new Date(f.properties.time).getTime(), +f.properties.value]).filter(p=>!isNaN(p[1])).sort((a,b)=>a[0]-b[0]);
    if (pts.length < 2 || !el()) { if (el()) el().textContent=''; return; }
    const W=210,H=54, t0=pts[0][0], t1=pts[pts.length-1][0], v0=Math.min(...pts.map(p=>p[1])), v1=Math.max(...pts.map(p=>p[1]))||1;
    const d = pts.map((p,i)=>`${i?'L':'M'}${((p[0]-t0)/(t1-t0||1)*W).toFixed(1)},${(H-2-(p[1]-v0)/((v1-v0)||1)*(H-6)).toFixed(1)}`).join('');
    el().innerHTML = `<svg class="spark" width="${W}" height="${H}"><path d="${d}" fill="none" stroke="#3fa9f5" stroke-width="2"/></svg>${pc==='00065'?'Stage':'Flow'}, last 2 days: ${v0.toFixed(2)} – ${v1.toFixed(2)}`;
  } catch (e) { if (el()) el().textContent = ''; }
}
function renderGaugeList() {
  const box = $('list'); const gs = Object.values(gauges);
  if (!gs.length) { box.innerHTML = '<div class="fine">No live gauges reached.</div>'; return; }
  box.innerHTML = '';
  const rank = (g)=> ({'In watershed':0,'Just downstream of watershed':1}[gaugeWhere(g)] ?? 2);
  gs.sort((a,b)=> rank(a)-rank(b) || (b.nws?1:0)-(a.nws?1:0) || a.name.localeCompare(b.name)).forEach(g=>{
    const d=document.createElement('div'); d.className='item';
    const cat = g.nws && g.nws.cat ? g.nws.cat : '';
    d.innerHTML = `<div><div class="nm">${esc(g.name)}</div><div class="meta">${gaugeWhere(g)} · ${g.flow!=null?Math.round(g.flow)+' cfs · ':''}${g.time?new Date(g.time).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}):''}${g.nws?' · NWS '+esc(g.nws.lid):''}</div></div><span class="badge ${/moderate|major/i.test(cat)?'b-hi':/minor/i.test(cat)?'b-md':/action/i.test(cat)?'b-lo':'b-ok'}">${g.stage!=null?g.stage.toFixed(2)+' ft':(cat||'live')}</span>`;
    d.onclick = ()=>{ map.setView([g.lat,g.lon], 15); };
    box.appendChild(d);
  });
}

// ------------------------------------------------------------------ exports
function download(name, text, type) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], {type})); a.download = name; document.body.appendChild(a); a.click(); setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
$('btnSar').onclick = () => {
  if (!scen) return;
  const tag = scen.meta.name;
  const feats = []
    .concat(scen.extent.features.map(f=>({type:'Feature', geometry:f.geometry, properties:{title:`Flooding ${f.properties.depth_class}`, description:tag, class:'Shape', fill: f.properties.depth_class==='3+ ft'?'#08308C':'#3182CE', 'fill-opacity':0.35, stroke:'#08308C', 'stroke-width':1}})))
    .concat(scen.roads.features.filter(f=>roadOK(f.properties)).map(f=>({type:'Feature', geometry:f.geometry, properties:{title:`${f.properties.name}: ${f.properties.max_ft.toFixed(1)} ft`, description:`${tag}. ~${f.properties.len_ft} ft of road under water.`, class:'Shape', stroke: f.properties.max_ft>=1?'#D7191C':'#F28E2B', 'stroke-width':5}})))
    .concat(scen.crossings.features.filter(f=>xingOK(f.properties)).map(f=>({type:'Feature', geometry:f.geometry, properties:{title:`${f.properties.road||'Road'} crossing: ${f.properties.overtop_ft.toFixed(1)} ft over`, description:`${f.properties.kind} ${f.properties.id} over ${f.properties.stream}. ${tag}`, class:'Marker', 'marker-color': f.properties.overtop_ft>1?'D7191C':'F28E2B', 'marker-symbol':'danger'}})));
  download(`ValleyCreek_${scen.meta.id.replace('+','_with_')}_SARTopo.geojson`, JSON.stringify({type:'FeatureCollection', features:feats}), 'application/geo+json');
};
$('btnCsv').onclick = () => {
  if (!scen) return;
  const rows = [['road','max_depth_ft','approx_length_ft','evac_route','major_road','owner','lat','lon','storm']];
  scen.roads.features.filter(f=>roadOK(f.properties)).sort((a,b)=>b.properties.max_ft-a.properties.max_ft).forEach(f=>{ const p=f.properties, c=f.geometry.coordinates[Math.floor(f.geometry.coordinates.length/2)];
    rows.push([p.name, p.max_ft, p.len_ft, p.evac?'yes':'', p.major?'yes':'', p.owner||'', c[1], c[0], scen.meta.name]); });
  download(`ValleyCreek_${scen.meta.id.replace('+','_with_')}_road_closures.csv`, rows.map(r=>r.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n'), 'text/csv');
};

// ------------------------------------------------------------------ tooltips
const tip = $('tip');
document.addEventListener('mouseover', e=>{ const t=e.target.closest('[data-tip]'); if(!t) return; tip.textContent=t.dataset.tip; tip.style.display='block'; const r=t.getBoundingClientRect(); tip.style.left=Math.min(r.left, window.innerWidth-310)+'px'; tip.style.top=(r.bottom+6)+'px'; });
document.addEventListener('mouseout', e=>{ if (e.target.closest('[data-tip]')) tip.style.display='none'; });

// ------------------------------------------------------------------ refresh cycle
async function refreshAll() {
  setUpdated('Updating live data…');
  radarNow.redraw && radarNow.redraw();
  await Promise.all([loadPastRain(), loadQpf(), loadAlerts(), loadGauges(), loadRiverForecasts()]);
  computeStatus();
  if ($('autoMatch').checked || !scen) await applyScenarioChoice();
  setUpdated('Updated ' + new Date().toLocaleString([], {weekday:'short', hour:'numeric', minute:'2-digit'}) + ' · refreshes every 5 min');
}
$('btnRefresh').onclick = refreshAll;

fillScenarioSelect();
buildPanel();
refreshAll();
setInterval(()=> { refreshAll(); if (loopOn) loopFrames.forEach(l=>l.redraw()); }, 5*60*1000);
})();
