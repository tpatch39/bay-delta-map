# Bay, Delta and Watershed Extents

An interactive map of what people mean by "the Bay," "the Delta," and the watersheds that feed them, drawn over live OpenStreetMap tiles. Part of the Water Organization Dashboard project.

- `index.html` — the map page (Leaflet, loaded from cdnjs)
- `data/layers.json` — all boundary and context layers as GeoJSON

## Data sources
- Legal Delta and Suisun Marsh boundaries: California Department of Water Resources, via the Interagency Ecological Program's [deltamapr](https://github.com/InteragencyEcologicalProgram/deltamapr)
- Bay and Delta waterways: DWR 1:24,000 hydrography (`hydro_delta_marsh`), via deltamapr
- Watersheds: USGS 1:250,000 hydrologic cataloging units, via [HUC8-GEOJSON](https://github.com/rc6750/HUC8-GEOJSON)
- Counties: [click_that_hood](https://github.com/codeforgermany/click_that_hood); rivers, lakes and towns: [Natural Earth](https://www.naturalearthdata.com/)
- Map tiles © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright)

Shapes are simplified for the web; areas are computed on the WGS84 ellipsoid.
