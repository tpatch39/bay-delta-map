"""Build data/orgs.json: organizations from the FMA 2026 Annual Conference attendee list
(organizations only; no personal names), categorized, tagged and given a service area."""
import json
from shapely.geometry import shape, mapping, Polygon
from shapely.ops import unary_union

OUT = "/home/claude/bay-delta-map/data/orgs.json"

CATS = {
    "fed": "Federal agencies",
    "state": "State agencies",
    "local": "Cities & counties",
    "district": "Flood control & water districts",
    "consult": "Consultants & contractors",
    "research": "Research",
    "academia": "Academia",
    "restore": "Restoration & conservation",
    "tech": "Technology & products",
    "services": "Legal & facilitation",
}
TOPICS = {
    "flood": "Flood risk & levees",
    "nfip": "Floodplain mapping & NFIP",
    "storm": "Stormwater",
    "emerg": "Emergency management & mitigation",
    "fcst": "Forecasting & climate science",
    "resto": "Restoration & habitat",
    "coast": "Coast & sea-level rise",
    "supply": "Water supply",
    "dams": "Dam safety",
    "geo": "Geotechnical & geohazards",
    "data": "GIS, data & software",
    "policy": "Policy, planning & finance",
}

# area: (kind, ref, label). kinds: state | bayDelta | centralValley | deltaPlan | bayArea | counties | city | point
# basis: "boundary" = the agency's own jurisdiction; "approx" = stand-in for a service area we do not have a boundary for;
#        "general" = firm or program that works across the area shown.
ORGS = [
    # Federal
    ("FEMA Region 9", "fed", ["nfip", "emerg", "policy"], ("state", None, "California, Nevada, Hawaii, Arizona and Pacific territories"), "general"),
    ("NOAA National Weather Service", "fed", ["fcst", "emerg"], ("state", None, "Statewide forecasts and warnings"), "general"),
    ("U.S. Army Corps of Engineers, Sacramento District", "fed", ["flood", "dams", "resto"], ("centralValley", None, "Sacramento and San Joaquin basins (the district also reaches into neighboring states)"), "approx"),
    # State
    ("California Department of Water Resources", "state", ["flood", "nfip", "supply", "dams", "fcst"], ("state", None, "Statewide"), "boundary"),
    ("California Geological Survey (Burned Watershed Geohazards)", "state", ["geo", "emerg"], ("state", None, "Statewide, focused on burned watersheds"), "boundary"),
    ("California Governor's Office of Emergency Services (Cal OES)", "state", ["emerg", "policy"], ("state", None, "Statewide"), "boundary"),
    ("California Coastal Commission", "state", ["coast", "policy"], ("state", None, "The outer coastal zone; San Francisco Bay itself is under BCDC"), "general"),
    ("Central Valley Flood Protection Board", "state", ["flood", "policy"], ("centralValley", None, "Central Valley flood system: Sacramento and San Joaquin valleys"), "approx"),
    ("Delta Stewardship Council", "state", ["policy", "resto", "flood", "fcst"], ("deltaPlan", None, "Legal Delta plus Suisun Marsh (Delta Plan area)"), "boundary"),
    ("Ocean Protection Council", "state", ["coast", "policy"], ("state", None, "Coast and ocean statewide, including San Francisco Bay"), "general"),
    ("State Coastal Conservancy", "state", ["resto", "coast"], ("state", None, "The coast and the nine-county Bay Area"), "general"),
    # Cities & counties
    ("City of Sacramento, Department of Utilities", "local", ["flood", "storm", "supply"], ("city", "Sacramento", "City of Sacramento"), "boundary"),
    ("City of Concord", "local", ["storm", "nfip"], ("city", "Concord", "City of Concord"), "boundary"),
    ("City of Elk Grove", "local", ["storm", "nfip"], ("city", "Elk Grove", "City of Elk Grove"), "boundary"),
    ("City of Lincoln", "local", ["storm", "nfip"], ("city", "Lincoln", "City of Lincoln"), "boundary"),
    ("City of Modesto", "local", ["storm"], ("city", "Modesto", "City of Modesto"), "boundary"),
    ("City of Mountain House", "local", ["storm", "supply"], ("city", "Mountain House", "City of Mountain House"), "boundary"),
    ("City of Mountain View", "local", ["storm", "coast"], ("city", "Mountain View", "City of Mountain View"), "boundary"),
    ("City of Petaluma", "local", ["flood", "storm"], ("city", "Petaluma", "City of Petaluma"), "boundary"),
    ("City of Pleasant Hill", "local", ["storm"], ("city", "Pleasant Hill", "City of Pleasant Hill"), "boundary"),
    ("City of Pleasanton", "local", ["storm"], ("city", "Pleasanton", "City of Pleasanton"), "boundary"),
    ("City of Roseville", "local", ["flood", "storm"], ("city", "Roseville", "City of Roseville"), "boundary"),
    ("City of Santa Rosa", "local", ["storm", "supply"], ("city", "Santa Rosa", "City of Santa Rosa"), "boundary"),
    ("City of Woodland", "local", ["flood", "storm"], ("city", "Woodland", "City of Woodland"), "boundary"),
    ("Sacramento County Department of Water Resources", "local", ["flood", "storm", "nfip"], ("counties", ["Sacramento"], "Sacramento County"), "boundary"),
    ("San Joaquin County (Public Works and Emergency Services)", "local", ["flood", "emerg", "nfip"], ("counties", ["San Joaquin"], "San Joaquin County"), "boundary"),
    ("Placer County", "local", ["flood", "nfip"], ("counties", ["Placer"], "Placer County"), "boundary"),
    ("Fresno County", "local", ["emerg"], ("counties", ["Fresno"], "Fresno County"), "boundary"),
    ("Madera County", "local", ["supply", "nfip"], ("counties", ["Madera"], "Madera County"), "boundary"),
    ("Merced County", "local", ["nfip"], ("counties", ["Merced"], "Merced County"), "boundary"),
    # Flood control & water districts
    ("Alameda County Flood Control & Water Conservation District", "district", ["flood", "storm"], ("counties", ["Alameda"], "Alameda County"), "boundary"),
    ("Contra Costa County Flood Control & Water Conservation District", "district", ["flood", "storm"], ("counties", ["Contra Costa"], "Contra Costa County"), "boundary"),
    ("Placer County Flood Control & Water Conservation District", "district", ["flood"], ("counties", ["Placer"], "Placer County"), "boundary"),
    ("Lake County Watershed Protection District", "district", ["flood", "resto"], ("counties", ["Lake"], "Lake County (Clear Lake and Cache Creek headwaters)"), "boundary"),
    ("Santa Clara Valley Water District (Valley Water)", "district", ["flood", "supply", "storm", "resto"], ("counties", ["Santa Clara"], "Santa Clara County"), "boundary"),
    ("East Bay Municipal Utility District", "district", ["supply"], ("counties", ["Alameda", "Contra Costa"], "Western Alameda and Contra Costa counties; supply from the Mokelumne River"), "approx"),
    ("Zone 7 Water Agency", "district", ["supply", "flood"], ("point", [37.682, -121.768], "Livermore-Amador Valley, eastern Alameda County"), "approx"),
    ("Sacramento Area Flood Control Agency", "district", ["flood"], ("counties", ["Sacramento"], "Sacramento region along the American and Sacramento rivers"), "approx"),
    ("West Sacramento Area Flood Control Agency", "district", ["flood"], ("city", "West Sacramento", "City of West Sacramento"), "boundary"),
    ("San Joaquin Area Flood Control Agency", "district", ["flood"], ("city", "Stockton", "Stockton metropolitan area"), "approx"),
    ("Lower San Joaquin Levee District", "district", ["flood"], ("counties", ["Merced"], "Upper San Joaquin River levees and bypasses, mainly Merced County"), "approx"),
    ("Levee Districts 1 & 9 of Sutter County", "district", ["flood"], ("city", "Yuba City", "Feather River west levee around Yuba City"), "approx"),
    ("Reclamation District 536 (Egbert Tract)", "district", ["flood"], ("point", [38.246, -121.763], "Egbert Tract, Solano County, north Delta"), "approx"),
    # Research
    ("Center for Western Weather and Water Extremes (CW3E), Scripps / UC San Diego", "research", ["fcst"], ("state", None, "Western U.S.; atmospheric rivers and reservoir operations"), "general"),
    ("Hydrologic Research Center", "research", ["fcst"], ("state", None, "National and international flash-flood guidance"), "general"),
    ("USACE Institute for Water Resources", "research", ["policy", "flood"], ("state", None, "National"), "general"),
    # Academia
    ("University of California, Berkeley", "academia", ["flood", "resto"], ("point", [37.872, -122.259], "Campus in Berkeley; research statewide"), "general"),
    ("Stanford University", "academia", ["flood", "fcst"], ("point", [37.428, -122.170], "Campus in Stanford; research statewide"), "general"),
    # Restoration & conservation
    ("River Partners", "restore", ["resto", "flood"], ("centralValley", None, "Central Valley river floodplains (also works in Southern California)"), "general"),
    ("Westervelt Ecological Services", "restore", ["resto"], ("state", None, "Mitigation and conservation banks across California"), "general"),
    ("Occidental Arts & Ecology Center WATER Institute", "restore", ["resto"], ("counties", ["Sonoma"], "Sonoma County and the North Bay"), "approx"),
    # Consultants & contractors
    ("AtkinsRéalis", "consult", ["flood", "dams"], ("state", None, "Works across California"), "general"),
    ("Arcadis", "consult", ["flood", "coast"], ("state", None, "Works across California"), "general"),
    ("Balance Hydrologics", "consult", ["resto", "flood"], ("bayDelta", None, "Northern California"), "general"),
    ("Bennett Engineering Services", "consult", ["flood", "storm"], ("bayDelta", None, "Northern California"), "general"),
    ("BKF Engineers", "consult", ["storm", "flood"], ("state", None, "Works across California"), "general"),
    ("Black & Veatch", "consult", ["supply", "storm"], ("state", None, "Works across California"), "general"),
    ("Blackburn Consulting", "consult", ["geo", "flood"], ("bayDelta", None, "Northern California"), "general"),
    ("Carollo Engineers", "consult", ["storm", "supply", "flood"], ("state", None, "Works across California"), "general"),
    ("Civil & Environmental Consultants", "consult", ["storm"], ("state", None, "Works across California"), "general"),
    ("Consor", "consult", ["flood", "fcst", "dams"], ("state", None, "Works across California"), "general"),
    ("CSG Consultants", "consult", ["nfip", "storm"], ("state", None, "Works across California"), "general"),
    ("DOWL", "consult", ["flood"], ("state", None, "Works across the western U.S."), "general"),
    ("Dudek", "consult", ["resto", "storm"], ("state", None, "Works across California"), "general"),
    ("ECORP Consulting", "consult", ["resto"], ("state", None, "Works across California"), "general"),
    ("ENGEO", "consult", ["geo", "flood"], ("state", None, "Works across California"), "general"),
    ("Environmental Science Associates (ESA)", "consult", ["resto", "coast", "flood"], ("state", None, "Works across California"), "general"),
    ("Forgen", "consult", ["flood"], ("state", None, "Construction contractor, national"), "general"),
    ("GEI Consultants", "consult", ["flood", "dams", "fcst", "supply"], ("state", None, "Works across California"), "general"),
    ("GHD", "consult", ["supply", "storm", "coast"], ("state", None, "Works across California"), "general"),
    ("Haley & Aldrich", "consult", ["geo"], ("state", None, "Works across California"), "general"),
    ("HDR", "consult", ["flood", "dams", "coast"], ("state", None, "Works across California"), "general"),
    ("Jacobs", "consult", ["flood", "supply", "policy"], ("state", None, "Works across California"), "general"),
    ("Kiewit", "consult", ["flood", "dams"], ("state", None, "Construction contractor, national"), "general"),
    ("Kimley-Horn", "consult", ["storm"], ("state", None, "Works across California"), "general"),
    ("Kjeldsen, Sinnock & Neudeck (KSN)", "consult", ["flood"], ("deltaPlan", None, "Delta reclamation districts and the San Joaquin Valley"), "general"),
    ("Kleinfelder", "consult", ["geo"], ("state", None, "Works across California"), "general"),
    ("Larsen Wurzel & Associates", "consult", ["policy"], ("bayDelta", None, "Flood and water agency finance, Northern California"), "general"),
    ("MBK Engineers", "consult", ["flood"], ("centralValley", None, "Central Valley and Delta flood system"), "general"),
    ("Mead & Hunt", "consult", ["flood", "dams"], ("state", None, "Works across California"), "general"),
    ("Michael Baker International", "consult", ["nfip", "flood"], ("state", None, "Works across California"), "general"),
    ("Moffatt & Nichol", "consult", ["coast"], ("state", None, "Works across California"), "general"),
    ("NCE", "consult", ["storm"], ("state", None, "Works across California"), "general"),
    ("PACE Advanced Water Engineering", "consult", ["flood", "storm"], ("state", None, "Works across California"), "general"),
    ("Schaaf & Wheeler", "consult", ["flood", "storm", "nfip"], ("bayArea", None, "Bay Area and statewide"), "general"),
    ("Simpson Gumpertz & Heger", "consult", ["flood"], ("state", None, "Works across California"), "general"),
    ("Stantec", "consult", ["flood", "storm", "resto"], ("state", None, "Works across California"), "general"),
    ("Tetra Tech", "consult", ["emerg", "flood"], ("state", None, "Works across California"), "general"),
    ("Towill", "consult", ["data"], ("state", None, "Surveying and mapping across California"), "general"),
    ("Verdantas", "consult", ["flood"], ("state", None, "Works across California"), "general"),
    ("WEST Consultants", "consult", ["flood", "nfip"], ("state", None, "Works across California"), "general"),
    ("West Yost", "consult", ["supply", "flood"], ("bayDelta", None, "Northern California"), "general"),
    ("Westwood Professional Services", "consult", ["storm"], ("state", None, "Works across California"), "general"),
    ("Wilson & Company", "consult", ["flood"], ("state", None, "Works across California"), "general"),
    ("Wood Rodgers", "consult", ["flood", "storm", "nfip"], ("bayDelta", None, "Northern California and statewide"), "general"),
    ("Woodard & Curran", "consult", ["supply", "storm"], ("state", None, "Works across California"), "general"),
    ("WRA Environmental Consultants", "consult", ["resto"], ("bayArea", None, "Bay Area and statewide"), "general"),
    # Legal & facilitation
    ("Downey Brand LLP", "services", ["policy"], ("bayDelta", None, "Flood and water law, Northern California"), "general"),
    ("Kearns & West", "services", ["policy"], ("state", None, "Facilitation and outreach across California"), "general"),
    # Technology & products
    ("Contech Engineered Solutions", "tech", ["storm"], ("state", None, "National"), "general"),
    ("Esri", "tech", ["data"], ("state", None, "National"), "general"),
    ("Ferguson Waterworks", "tech", ["storm", "supply"], ("state", None, "National"), "general"),
    ("Flood Control International", "tech", ["flood"], ("state", None, "Flood barriers, international"), "general"),
    ("Forerunner", "tech", ["nfip", "data"], ("state", None, "Floodplain management software, national"), "general"),
    ("Hanes Geo Components", "tech", ["geo"], ("state", None, "Geosynthetics, regional supplier"), "general"),
    ("Hohonu", "tech", ["data", "coast"], ("state", None, "Water-level sensors, national"), "general"),
    ("Jensen Infrastructure", "tech", ["storm"], ("state", None, "Precast stormwater products, western U.S."), "general"),
    ("Sanborn Map Company", "tech", ["data"], ("state", None, "Mapping and LiDAR, national"), "general"),
    ("Scalgo", "tech", ["data", "nfip"], ("state", None, "Flood screening software, international"), "general"),
    ("SOLMAX", "tech", ["geo", "flood"], ("state", None, "Geosynthetics, international"), "general"),
    ("TUFLOW", "tech", ["data", "flood"], ("state", None, "Flood modeling software, international"), "general"),
    ("Watershed Geo", "tech", ["geo", "flood"], ("state", None, "Erosion control products, national"), "general"),
]

NOT_MAPPED = {
    "Outside the Bay–Delta scope (Southern California, Nevada, Hawaii or elsewhere)": [
        "Albert A. Webb Associates", "Atchafalaya Basin Levee District", "City of Chula Vista", "City of Henderson",
        "City of Huntington Beach", "City of Long Beach", "City of Los Angeles", "City of Moreno Valley",
        "City of Newport Beach", "City of San Diego", "City of Santa Maria", "City of Simi Valley",
        "City of Thousand Oaks", "Clark County Regional Flood Control District", "County of Maui",
        "County of San Diego Flood Control", "San Bernardino County (Public Works, Flood Control District)",
        "County of San Luis Obispo", "Santa Barbara County Flood Control & Water Conservation District",
        "Ventura County Public Works", "Los Angeles County Public Works", "LA Sanitation and Environment",
        "OC Public Works", "Orange County Water District", "Riverside County Flood Control & Water Conservation District",
        "Monterey County Water Resources Agency", "Kings River Conservation District (Tulare basin)",
        "Nevada Division of Water Resources", "University of California, Irvine", "Craftwater", "Q3 Consulting",
        "R&F Engineering", "Rick Engineering", "Tory R. Walker Engineering", "River Focus", "Odin Environmental Solutions",
        "Jensen Design & Survey (Sanbell)", "Wallace Group", "Weija Gbawe Municipal Assembly (Ghana)",
    ],
    "Couldn't confirm where they work": [
        "Geronimo Engineering", "Hill Storm Water Engineering", "Kasraie Consulting", "MRC LLC", "Swift Response",
        "Walker Floodplain Management", "X Engineering and Consulting", "“FM” (listed without a full name)",
    ],
}

# City outlines from OpenStreetMap (Nominatim), simplified
cities = {}
for line in open("/home/claude/fma/cities.txt"):
    k, v = line.strip().split("=")
    pts = [tuple(map(float, p.split())) for p in v.split(",")]
    cities[k] = [[list(p) for p in pts + [pts[0]]]]

st = json.load(open("/home/claude/data/states.geojson"))
ca = shape(next(f for f in st["features"] if f["properties"]["name"] == "California")["geometry"]).simplify(0.02)
def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], (list, tuple)) else [round(c[0], 3), round(c[1], 3)]
ca_geo = mapping(ca)

orgs = []
for name, cat, topics, (kind, ref, label), basis in ORGS:
    assert cat in CATS and all(t in TOPICS for t in topics), name
    if kind == "city":
        assert ref in cities, ref
    orgs.append({"name": name, "cat": cat, "topics": topics, "area": {"kind": kind, "ref": ref, "label": label}, "basis": basis})

out = {
    "source": "Floodplain Management Association, 2026 Annual Conference List of Attendees (organizations only)",
    "sourceUrl": "https://cdn.ymaws.com/floodplain.org/resource/resmgr/FMA_2026_List_of_Attendees.pdf",
    "cats": CATS, "topics": TOPICS, "orgs": orgs, "notMapped": NOT_MAPPED,
    "cities": {k: {"type": "Polygon", "coordinates": v} for k, v in cities.items()},
    "california": {"type": ca_geo["type"], "coordinates": rnd(ca_geo["coordinates"])},
}
s = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
open(OUT, "w").write(s)
from collections import Counter
print(len(orgs), "orgs", len(s) // 1024, "KB")
print(Counter(o["cat"] for o in orgs))
print(Counter(o["area"]["kind"] for o in orgs))
print(sum(len(v) for v in NOT_MAPPED.values()), "not mapped")
