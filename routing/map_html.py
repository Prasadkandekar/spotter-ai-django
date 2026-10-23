"""Self-contained Leaflet page. Tiles come from OpenStreetMap (free); data is embedded, so no extra API calls."""
import json
from html import escape

_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fuel route: __TITLE__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
 html,body{height:100%;margin:0;font-family:system-ui,sans-serif}
 #map{position:absolute;inset:0}
 #panel{position:absolute;z-index:1000;top:12px;right:12px;max-width:320px;background:#fff;padding:12px 14px;
        border-radius:8px;box-shadow:0 2px 10px rgba(0,0,0,.25);font-size:13px;line-height:1.45}
 #panel h1{font-size:15px;margin:0 0 6px} #panel table{border-collapse:collapse;width:100%}
 #panel td{padding:2px 0;vertical-align:top} #panel td:last-child{text-align:right;font-weight:600}
</style></head><body>
<div id="map"></div><div id="panel"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const map = L.map('map');
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const line = L.geoJSON(D.route.geometry,{style:{color:'#2563eb',weight:5,opacity:.85}}).addTo(map);
map.fitBounds(line.getBounds(),{padding:[40,40]});
const pin=(c,t)=>L.divIcon({className:'',html:`<div style="background:${c};color:#fff;border:2px solid #fff;border-radius:50%;width:26px;height:26px;line-height:22px;text-align:center;font-weight:700;box-shadow:0 1px 4px rgba(0,0,0,.5)">${t}</div>`,iconSize:[26,26],iconAnchor:[13,13]});
L.marker([D.start.location.lat,D.start.location.lng],{icon:pin('#16a34a','A')}).addTo(map).bindPopup('<b>Start</b><br>'+D.start.resolved);
L.marker([D.finish.location.lat,D.finish.location.lng],{icon:pin('#dc2626','B')}).addTo(map).bindPopup('<b>Finish</b><br>'+D.finish.resolved);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
D.fuel_stops.forEach(s=>L.marker([s.location.lat,s.location.lng],{icon:pin('#f59e0b',s.stop)}).addTo(map).bindPopup(
 `<b>${esc(s.name)}</b><br>${esc(s.address)}<br>${esc(s.city)}, ${esc(s.state)}<br>Mile ${s.mile_marker}<br>`+
 `$${s.price_per_gallon.toFixed(3)}/gal &middot; ${s.gallons_purchased} gal &middot; <b>$${s.cost.toFixed(2)}</b>`));
const S=D.summary;
document.getElementById('panel').innerHTML=`<h1>${esc(D.start.resolved)} &rarr; ${esc(D.finish.resolved)}</h1><table>
<tr><td>Distance</td><td>${D.route.distance_miles} mi</td></tr>
<tr><td>Fuel stops</td><td>${S.number_of_fuel_stops}</td></tr>
<tr><td>Fuel used</td><td>${S.total_gallons_used} gal</td></tr>
<tr><td>Total fuel cost</td><td>$${S.total_fuel_cost.toFixed(2)}</td></tr></table>`;
</script></body></html>
"""


def render_map_html(result: dict) -> str:
    # "</" is escaped so station names can never terminate the <script> block.
    data = json.dumps(result, separators=(",", ":")).replace("</", "<\\/")
    title = escape(f'{result["start"]["resolved"]} to {result["finish"]["resolved"]}')
    return _TEMPLATE.replace("__DATA__", data).replace("__TITLE__", title)
