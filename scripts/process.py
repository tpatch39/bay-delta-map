import json, glob, re, sys
import shapefile, rdata, warnings
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, Point, box
from shapely.ops import unary_union, transform
from pyproj import Geod, Transformer

warnings.filterwarnings("ignore")
D = "/home/claude/data"
OUT = "/home/claude/site/data"
geod = Geod(ellps="WGS84")

def area_km2(g):
    return abs(geod.geometry_area_perimeter(g)[0]) / 1e6

def rnd(g, nd=4):
    def r(c):
        if isinstance(c[0], (list, tuple)):
            return [r(x) for x in c]
        return [round(c[0], nd), round(c[1], nd)]
    m = mapping(g)
    return {"type": m["type"], "coordinates": r(m["coordinates"])}

def feat(g, props, tol, nd=4):
    if g.geom_type == "GeometryCollection":
        parts = [x for x in g.geoms if x.geom_type in ("Polygon", "MultiPolygon")] or [x for x in g.geoms if "Line" in x.geom_type]
        if not parts: return None
        g = unary_union(parts)
    g = g.simplify(tol, preserve_topology=True)
    if g.is_empty:
        return None
    return {"type": "Feature", "properties": props, "geometry": rnd(g, nd)}

def fc(feats):
    return {"type": "FeatureCollection", "features": [f for f in feats if f]}

# ---------- R objects (sf) -> shapely ----------
def sf_geoms(name):
    p = rdata.parser.parse_file(f"{D}/deltamapr/data/{name}.rda")
    df = rdata.conversion.convert(p)[name]
    return df

def to_poly(obj):
    # sfg POLYGON = list of rings (n x 2 arrays); MULTIPOLYGON = list of polygons
    import numpy as np
    def ring(a):
        a = np.asarray(a)
        return [tuple(x) for x in a[:, :2]]
    def poly(rings):
        rings = list(rings)
        return Polygon(ring(rings[0]), [ring(x) for x in rings[1:]])
    lst = list(obj)
    first = np.asarray(lst[0]) if not isinstance(lst[0], list) else None
    if first is not None and first.ndim == 2:
        return poly(lst)
    return MultiPolygon([poly(p) for p in lst])

import numpy as np
merc = Transformer.from_crs(3857, 4326, always_xy=True)

def maybe_merc(g):
    x0, y0, x1, y1 = g.bounds
    if abs(x0) > 360:
        return transform(lambda x, y, z=None: merc.transform(x, y), g)
    return g

delta_df = sf_geoms("R_Delta")
legal_delta = unary_union([maybe_merc(to_poly(g)).buffer(0) for g in delta_df["geometry"]])
suisun_df = sf_geoms("R_Suisun")
suisun = [(loc, maybe_merc(to_poly(g)).buffer(0)) for loc, g in zip(suisun_df["LOCATION"], suisun_df["geometry"])]
suisun_all = unary_union([g for _, g in suisun])
print("legal delta", legal_delta.bounds, round(area_km2(legal_delta)), "km2")
print("suisun", suisun_all.bounds, round(area_km2(suisun_all)), "km2")

# ---------- Waterways ----------
r = shapefile.Reader(f"{D}/deltamapr/data-raw/WW_Delta/hydro_delta_marsh.shp")
ww = [(rec["HNAME"].strip(), rec["TYPE"], shape(s.__geo_interface__).buffer(0)) for rec, s in zip(r.records(), r.shapes())]
inside = [w for w in ww if legal_delta.buffer(0.002).contains(w[2].representative_point())]
outside = [w for w in ww if w not in inside]
print("waterways inside delta", len(inside), "outside", len(outside))

BAYS = {
    "SAN FRANCISCO BAY": "San Francisco Bay (Central & South)",
    "RICHARDSON BAY": "San Francisco Bay (Central & South)",
    "SAN PABLO BAY": "San Pablo Bay",
    "SUISUN BAY": "Suisun & Grizzly Bays",
    "GRIZZLY BAY": "Suisun & Grizzly Bays",
    "HONKER BAY": "Suisun & Grizzly Bays",
}
groups = {}
for name, typ, g in outside:
    key = BAYS.get(name)
    if key is None:
        # Carquinez Strait has no name in the source; anything else is a tributary/slough
        key = "Tributaries, sloughs & marsh channels"
    groups.setdefault(key, []).append(g)
bay_feats = []
bay_total = unary_union([g for _, _, g in outside])
for key, gs in groups.items():
    u = unary_union(gs)
    bay_feats.append(feat(u, {"name": key, "km2": round(area_km2(u))}, 0.0004))
print({k: round(area_km2(unary_union(v))) for k, v in groups.items()})
delta_ww = unary_union([g for _, _, g in inside])
delta_named = {}
for name, typ, g in inside:
    delta_named.setdefault(name or "Unnamed channel", []).append(g)
delta_feats = [feat(unary_union(v), {"name": k.title()}, 0.0002, 5) for k, v in delta_named.items()]

# ---------- Counties ----------
cty = json.load(open(f"{D}/ca_counties.geojson"))
BAY9 = ["Alameda", "Contra Costa", "Marin", "Napa", "San Francisco", "San Mateo", "Santa Clara", "Solano", "Sonoma"]
DELTA5 = ["Contra Costa", "Sacramento", "San Joaquin", "Solano", "Yolo"]
counties = {f["properties"]["name"]: shape(f["geometry"]).buffer(0) for f in cty["features"]}
probe = Point(-122.33, 37.70)
print("bay probe inside a county?", any(g.contains(probe) for g in counties.values()))
county_feats = [feat(g, {"name": n, "bay9": n in BAY9, "delta5": n in DELTA5}, 0.001) for n, g in counties.items()]
bay9 = unary_union([counties[n] for n in BAY9])
print("bay9 km2", round(area_km2(bay9)))

# ---------- Watersheds (HUC8 -> HUC4) ----------
HUC4 = {"1802": "Sacramento", "1803": "Tulare–Buena Vista Lakes", "1804": "San Joaquin", "1805": "San Francisco Bay"}
h8 = []
for f in sorted(glob.glob(f"{D}/HUC8-GEOJSON/geojson/*.geojson")):
    d = json.load(open(f))
    gs, name, code = [], None, None
    for ft in d["features"]:
        desc = ft["properties"].get("description", "")
        m = re.search(r"CAT_NAME</b>.*?<font[^>]*>([^<]*)</font>", desc)
        if m: name = m.group(1).strip()
        code = ft["properties"]["name"]
        gs.append(shape(ft["geometry"]).buffer(0))
    g = unary_union(gs)
    g = transform(lambda x, y, z=None: (x, y), g)
    name = re.sub(r"\.\s*California.*$|\.\s*Oregon.*$|\.\s*Nevada.*$", "", name or "").strip(" .")
    name = re.sub(r"\.\s*Californi.*$|\s+California$", "", name).replace("- ", "-").replace("Consumnes", "Cosumnes")
    h8.append((code, name, g))
COASTAL = {"18050005", "18050006"}
huc8_feats = [feat(g, {"code": c, "name": n, "huc4": c[:4], "km2": round(area_km2(g)), "coastal": c in COASTAL}, 0.003) for c, n, g in h8]
huc4 = {}
for code, name, g in h8:
    huc4.setdefault(code[:4], []).append(g)
huc4_geom = {k: unary_union(v).buffer(0.0005).buffer(-0.0005) for k, v in huc4.items()}
huc4_feats = [feat(g, {"code": k, "name": HUC4[k], "km2": round(area_km2(g)), "n": len(huc4[k])}, 0.003) for k, g in huc4_geom.items()]
baydelta_ws = unary_union([huc4_geom[k] for k in ("1802", "1804", "1805")]).buffer(0.002).buffer(-0.002)
for k, g in huc4_geom.items():
    print("HUC4", k, HUC4[k], round(area_km2(g)), "km2", len(huc4[k]), "units")
print("Bay-Delta watershed km2", round(area_km2(baydelta_ws)))
ca = shape(next(f for f in json.load(open(f"{D}/states.geojson"))["features"] if f["properties"]["name"] == "California")["geometry"])
ca_km2 = area_km2(ca)
bd_in_ca = area_km2(baydelta_ws.intersection(ca))
print("CA km2", round(ca_km2), "Bay-Delta share in CA", round(100 * bd_in_ca / ca_km2, 1), "%")

# ---------- Context: states, rivers, lakes, places ----------
view = box(-124.6, 34.6, -117.6, 42.3)
states = json.load(open(f"{D}/states.geojson"))
state_feats = [feat(shape(f["geometry"]), {"name": f["properties"]["name"]}, 0.004) for f in states["features"] if f["properties"]["name"] != "California"]

def clip_lines(path, minscale=99):
    out = []
    for f in json.load(open(path))["features"]:
        if not f.get("geometry"): continue
        g = shape(f["geometry"])
        if not g.intersects(view): continue
        p = f["properties"]
        nm = p.get("name") or p.get("name_en") or ""
        if p.get("scalerank", 0) > minscale: continue
        out.append(feat(g.intersection(view), {"name": nm}, 0.002))
    return out
rivers = clip_lines(f"{D}/ne_10m_rivers_lake_centerlines.geojson") + clip_lines(f"{D}/ne_10m_rivers_north_america.geojson")
lakes = []
for p in ("ne_10m_lakes", "ne_10m_lakes_north_america"):
    for f in json.load(open(f"{D}/{p}.geojson"))["features"]:
        g = shape(f["geometry"]).buffer(0)
        if g.intersects(view):
            lakes.append(feat(g.intersection(view), {"name": f["properties"].get("name") or ""}, 0.002))
places = []
for f in json.load(open(f"{D}/ne_10m_populated_places_simple.geojson"))["features"]:
    p = f["properties"]; x, y = f["geometry"]["coordinates"]
    if view.contains(Point(x, y)) and p.get("adm1name") == "California" and (p["scalerank"] <= 6 or p["name"] in ("Antioch", "Vallejo", "Davis", "Martinez", "Rio Vista", "Tracy", "Napa", "Santa Rosa", "Stockton", "Modesto", "Redding", "Merced", "Yuba City", "Lodi", "South Lake Tahoe")):
        places.append({"type": "Feature", "properties": {"name": p["name"], "rank": p["scalerank"], "pop": p.get("pop_max")}, "geometry": {"type": "Point", "coordinates": [round(x, 4), round(y, 4)]}})
print("rivers", len(rivers), "lakes", len(lakes), "places", len(places), sorted(x["properties"]["name"] for x in places))

layers = {
    "legalDelta": fc([feat(legal_delta, {"name": "Legal Delta", "km2": round(area_km2(legal_delta))}, 0.0003)]),
    "suisun": fc([feat(g, {"zone": loc}, 0.0003) for loc, g in suisun]),
    "suisunTotal": round(area_km2(suisun_all)),
    "deltaPlan": fc([feat(unary_union([legal_delta, suisun_all]).buffer(0.001).buffer(-0.001), {"name": "Delta Plan area"}, 0.0004)]),
    "deltaPlanKm2": round(area_km2(unary_union([legal_delta, suisun_all]))),
    "bayWater": fc(bay_feats),
    "bayWaterKm2": round(area_km2(bay_total)),
    "deltaWater": fc(delta_feats),
    "deltaWaterKm2": round(area_km2(delta_ww)),
    "counties": fc(county_feats),
    "bay9": fc([feat(bay9.buffer(0.002).buffer(-0.002), {"name": "Nine-county Bay Area", "km2": round(area_km2(bay9))}, 0.001)]),
    "huc8": fc(huc8_feats),
    "huc4": fc(huc4_feats),
    "bayDeltaWs": fc([feat(baydelta_ws, {"name": "Bay-Delta watershed", "km2": round(area_km2(baydelta_ws)), "caShare": round(100 * bd_in_ca / ca_km2)}, 0.003)]),
    "states": fc(state_feats),
    "rivers": fc(rivers),
    "lakes": fc(lakes),
    "places": fc(places),
}
import os
os.makedirs(OUT, exist_ok=True)
s = json.dumps(layers, separators=(",", ":"))
open(f"{OUT}/layers.json", "w").write(s)
print("layers.json", len(s) // 1024, "KB")
for k, v in layers.items():
    print(k, len(json.dumps(v)) // 1024, "KB")
