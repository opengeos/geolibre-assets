"""Build 10 GeoLibre projects from open data into ~/Downloads/geolibre-open-data-maps."""

import csv
import io
import json
import math
import pathlib
import urllib.request
from collections import Counter, defaultdict

import geolibre.geolibre as _gl
from geolibre import Map

# Headless authoring only: skip starting the bundled app server.
_gl.serve_app = lambda *_a, **_k: "http://localhost/"
from geolibre.authoring import build_choropleth_style
from geolibre.project import ensure_plugins_block

OUT = pathlib.Path("~/Downloads/geolibre-open-data-maps").expanduser()
OUT.mkdir(parents=True, exist_ok=True)

GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best"
ESRI_IMAGERY = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ESRI_ATTR = "Esri, Maxar, Earthstar Geographics, and the GIS User Community"


def fetch(url, timeout=180):
    """Download a URL and return its bytes.

    Args:
        url: The URL to fetch.
        timeout: Socket timeout in seconds.

    Returns:
        The response body.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "geolibre-open-data-demo"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read()


def fetch_json(url):
    """Download and decode a JSON document.

    Args:
        url: The URL to fetch.

    Returns:
        The decoded JSON value.
    """
    return json.loads(fetch(url))


def fc(features):
    """Wrap features in a FeatureCollection.

    Args:
        features: A list of GeoJSON features.

    Returns:
        A GeoJSON FeatureCollection dict.
    """
    return {"type": "FeatureCollection", "features": features}


def point(lng, lat, **props):
    """Build a GeoJSON point feature.

    Args:
        lng: Longitude.
        lat: Latitude.
        **props: Feature properties.

    Returns:
        A GeoJSON Feature dict.
    """
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lng, 5), round(lat, 5)]},
        "properties": props,
    }


def round_coords(obj, nd=3):
    """Round every coordinate in a nested coordinate array.

    Args:
        obj: A GeoJSON coordinate array (any nesting).
        nd: Decimal places to keep.

    Returns:
        The rounded coordinate array.
    """
    if isinstance(obj, (int, float)):
        return round(obj, nd)
    return [round_coords(o, nd) for o in obj]


def save(m, slug, title, description):
    """Name the project, attach a description and write a compact project file.

    Args:
        m: The map to save.
        slug: File name stem.
        title: Project display name.
        description: Human readable description stored in project metadata.
    """
    m.project["name"] = title
    m.project.setdefault("metadata", {})["description"] = description
    path = OUT / f"{slug}.geolibre.json"
    project = m.to_project()  # credentials stripped
    # Pin the plugin set so the map opens the same regardless of which plugin
    # panels the viewer last had open.
    ensure_plugins_block(project)
    path.write_text(json.dumps(project, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    Map().load_project(str(path))  # validates
    print(f"wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")


def map_legend(m, title, *, custom=None, hide=(), position="bottom-left"):
    """Show the project's map legend (Controls > Legend).

    Vector layers contribute rows derived from their own symbology. Raster tile
    layers carry no class information, so their rows are hand-written through
    ``customEntries`` keyed by the layer id; layers with nothing to explain are
    hidden through an entry override.

    Args:
        m: The map to update.
        title: Legend heading.
        custom: Mapping of layer name to ``{"title": ..., "items": [...]}``.
        hide: Names of visible layers to leave out of the legend.
        position: Map corner for the legend panel.
    """
    m.set_map_legend(title, position=position)
    legend = m.project["legend"]
    ids = {layer.name: layer.id for layer in m.layers}
    if custom:
        legend["customEntries"] = {ids[name]: entry for name, entry in custom.items()}
    for name in hide:
        legend["overrides"][ids[name]] = {"hidden": True}


def items(pairs, shape="square"):
    """Build hand-written legend items.

    Args:
        pairs: Mapping of label to CSS color, in display order.
        shape: Swatch shape: ``"square"``, ``"circle"`` or ``"line"``.

    Returns:
        A list of legend item dicts.
    """
    return [{"label": k, "color": v, "shape": shape} for k, v in pairs.items()]


# ---------------------------------------------------------------- 1. Asthma
def asthma():
    """US county adult asthma and COPD prevalence (CDC PLACES)."""
    counties = fetch_json(
        "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    )
    layers = {}
    for measure in ("CASTHMA", "COPD"):
        rows = fetch_json(
            "https://data.cdc.gov/resource/swc5-untb.json?"
            f"measureid={measure}&datavaluetypeid=AgeAdjPrv&$limit=5000"
        )
        layers[measure] = {r["locationid"]: r for r in rows}
    feats = []
    for f in counties["features"]:
        a = layers["CASTHMA"].get(f["id"])
        c = layers["COPD"].get(f["id"])
        if not a or "data_value" not in a:
            continue
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": f["geometry"]["type"],
                             "coordinates": round_coords(f["geometry"]["coordinates"])},
                "properties": {
                    "county": f"{a['locationname']}, {a['stateabbr']}",
                    "asthma_pct": float(a["data_value"]),
                    "copd_pct": float(c["data_value"]) if c and "data_value" in c else None,
                    "population": int(a["totalpopulation"]),
                },
            }
        )
    data = fc(feats)
    m = Map(center=(-96, 38.5), zoom=3.6, basemap="positron")
    m.set_projection("mercator")
    popup = [
        {"field": "county", "label": "County"},
        {"field": "asthma_pct", "label": "Adult asthma (age-adj.)", "kind": "number", "suffix": " %"},
        {"field": "copd_pct", "label": "COPD (age-adj.)", "kind": "number", "suffix": " %"},
        {"field": "population", "label": "Population", "kind": "number", "thousands": True},
    ]
    m.add_choropleth(
        data, "copd_pct", name="COPD prevalence (%)", class_count=7, colormap="purples",
        scheme="quantile", strokeColor="#ffffff", strokeWidth=0.2, fillOpacity=0.85,
        popup=popup, tooltip=True,
    )
    m.set_layer_visibility("COPD prevalence (%)", False)
    m.add_choropleth(
        data, "asthma_pct", name="Adult asthma prevalence (%)", class_count=7,
        colormap="reds", scheme="quantile", strokeColor="#ffffff", strokeWidth=0.2,
        fillOpacity=0.85, popup=popup, tooltip=True,
    )
    map_legend(m, "Adult prevalence")
    save(m, "01_us_asthma_copd_cdc_places", "US Adult Asthma & COPD by County",
         "Environmental health: county-level age-adjusted prevalence of current asthma and "
         "COPD among US adults, CDC PLACES 2025 release (BRFSS 2023). Toggle COPD in the "
         "layer panel.")


# ---------------------------------------------------------- 2. NO2 change
def no2():
    """Ground-level NO2, 1996-1998 vs 2010-2012 (NASA SEDAC via GIBS)."""
    m = Map(center=(10, 35), zoom=2.3, basemap="dark")
    tpl = GIBS + "/Ground_Level_Nitrogen_Dioxide_3_Year_Running_Mean_{p}/default/GoogleMapsCompatible_Level7/{{z}}/{{y}}/{{x}}.png"
    attr = "NASA SEDAC / GIBS — Geddes et al. 2016"
    m.add_tile_layer(tpl.format(p="1996-1998"), name="NO₂ 1996–1998", attribution=attr,
                     opacity=0.85, maxZoom=7)
    m.add_tile_layer(tpl.format(p="2010-2012"), name="NO₂ 2010–2012", attribution=attr,
                     opacity=0.85, maxZoom=7)
    today = GIBS + "/TROPOMI_L2_Nitrogen_Dioxide_Tropospheric_Column/default/2026-09-25/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png"
    m.add_tile_layer(today, name="Sentinel-5P TROPOMI NO₂ (2026-09-25)", attribution="ESA / NASA GIBS",
                     opacity=0.8)
    m.set_layer_visibility("Sentinel-5P TROPOMI NO₂ (2026-09-25)", False)
    for lyr in m.layers:
        m.set_layer_opacity(lyr, 0.85)
    m.split_map(left_layers=[m.find_layer("NO₂ 1996–1998")], right_layers=[m.find_layer("NO₂ 2010–2012")])
    map_legend(m, "Ground-level NO₂", hide=["NO₂ 1996–1998"], custom={
        "NO₂ 2010–2012": {"title": "NO₂, both periods (ppb)", "items": items({
            "< 0.3": "#ebeabb", "0.8": "#f4f381", "1.5": "#fcfc20", "2.5": "#ff9900",
            "4": "#ff0000", "6": "#cf048e", "12": "#8e0be0", "25+": "#2818b9"})}})
    save(m, "02_no2_air_pollution_1997_vs_2011", "Ground-level NO2: 1997 vs 2011",
         "Environmental health & change: satellite-derived ground-level nitrogen dioxide, "
         "1996–1998 vs 2010–2012 swipe. Watch NO₂ fall over the US/Europe and surge over "
         "China, India and the Middle East. A recent TROPOMI daily layer is included.")


# --------------------------------------------------------------- 3. Fires
def fires():
    """NASA FIRMS VIIRS active fires, last 7 days."""
    raw = fetch(
        "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_7d.csv"
    ).decode()
    cells = {}
    for r in csv.DictReader(io.StringIO(raw)):
        if r["confidence"] == "l":
            continue
        key = (round(float(r["longitude"]) * 10), round(float(r["latitude"]) * 10))
        c = cells.setdefault(key, {"n": 0, "frp": 0.0, "max": 0.0, "last": ""})
        c["n"] += 1
        c["frp"] += float(r["frp"])
        c["max"] = max(c["max"], float(r["frp"]))
        c["last"] = max(c["last"], r["acq_date"])
    pts = [point(k[0] / 10, k[1] / 10, detections=c["n"], frp=round(c["frp"], 1),
                 weight=round(min(c["frp"], 150) / 150, 3),
                 max_frp=round(c["max"], 1), last_seen=c["last"])
           for k, c in cells.items()]
    print(f"  fires: {len(pts)} 0.1-degree cells")
    m = Map(center=(20, 5), zoom=1.8, basemap="dark")
    m.add_heatmap(fc(pts), name="Fire radiative power heatmap", radius=8, intensity=0.7,
                  color_ramp="inferno", weight_field="weight", maxZoom=6)
    style = build_choropleth_style([p["properties"]["frp"] for p in pts], "frp",
                                   class_count=6, colormap="inferno", scheme="quantile")
    breaks = [0, 5, 20, 50, 200, 1000]
    style["vectorStyleStops"] = [{"value": v, "color": s["color"]}
                                 for v, s in zip(breaks, style["vectorStyleStops"])]
    m.add_geojson(fc(pts), name="Active fire cells (0.1°, total FRP)", circleRadius=3.5,
                  strokeWidth=0, minZoom=5, **style,
                  popup=[{"field": "detections", "label": "VIIRS detections"},
                         {"field": "frp", "label": "Total fire radiative power", "kind": "number", "suffix": " MW"},
                         {"field": "max_frp", "label": "Strongest detection", "suffix": " MW", "kind": "number"},
                         {"field": "last_seen", "label": "Last detected"}],
                  tooltip=True)
    map_legend(m, "Active fires")
    save(m, "03_global_wildfires_firms_7day", "Global Wildfires — Last 7 Days",
         "Environmental change & health: every NOAA-20 VIIRS active-fire detection of the "
         "last 7 days (NASA FIRMS), binned to 0.1° cells: an FRP-weighted heatmap globally that "
         "resolves into fire cells colored by total radiative power when you zoom past level 5.")


# ------------------------------------------------------------- 4. Flights
def slerp_line(a, b, n=48):
    """Great-circle coordinates between two lon/lat points, split at the antimeridian.

    Args:
        a: Start (lng, lat).
        b: End (lng, lat).
        n: Number of segments.

    Returns:
        A list of coordinate lists (one per antimeridian-free part).
    """
    def xyz(p):
        lo, la = map(math.radians, p)
        return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))

    p1, p2 = xyz(a), xyz(b)
    d = math.acos(max(-1, min(1, sum(x * y for x, y in zip(p1, p2)))))
    if d == 0:
        return [[list(a), list(b)]]
    parts, cur, prev = [], [], None
    for i in range(n + 1):
        t = i / n
        s1, s2 = math.sin((1 - t) * d) / math.sin(d), math.sin(t * d) / math.sin(d)
        x, y, z = (s1 * u + s2 * v for u, v in zip(p1, p2))
        lng, lat = math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))
        if prev is not None and abs(lng - prev) > 180:
            parts.append(cur)
            cur = []
        cur.append([round(lng, 3), round(lat, 3)])
        prev = lng
    parts.append(cur)
    return [p for p in parts if len(p) > 1]


def flights():
    """Global airline route network (OpenFlights)."""
    airports = {}
    for r in csv.reader(io.StringIO(fetch(
            "https://raw.githubusercontent.com/jpatokal/openflights/master/data/airports.dat").decode())):
        try:
            airports[r[0]] = (r[1], r[2], r[3], r[4], float(r[7]), float(r[6]))
        except (ValueError, IndexError):
            pass
    pairs, degree = Counter(), Counter()
    for r in csv.reader(io.StringIO(fetch(
            "https://raw.githubusercontent.com/jpatokal/openflights/master/data/routes.dat").decode())):
        s, d = r[3], r[5]
        if s in airports and d in airports and s != d:
            pairs[tuple(sorted((s, d)))] += 1
            degree[s] += 1
            degree[d] += 1
    lines = []
    for (s, d), n in pairs.most_common(4000):
        a, b = airports[s], airports[d]
        parts = slerp_line((a[4], a[5]), (b[4], b[5]))
        lines.append({
            "type": "Feature",
            "geometry": {"type": "MultiLineString", "coordinates": parts},
            "properties": {"route": f"{a[3] or a[0]} ↔ {b[3] or b[0]}",
                           "from": f"{a[0]}, {a[2]}", "to": f"{b[0]}, {b[2]}",
                           "airline_routes": n},
        })
    lines.sort(key=lambda f: f["properties"]["airline_routes"])
    hubs = [point(airports[k][4], airports[k][5], airport=airports[k][0], city=airports[k][1],
                  country=airports[k][2], iata=airports[k][3], routes=v)
            for k, v in degree.most_common(1500)]
    m = Map(center=(30, 32), zoom=1.8, basemap="dark")
    style = build_choropleth_style([f["properties"]["airline_routes"] for f in lines],
                                   "airline_routes", class_count=6, colormap="plasma",
                                   scheme="quantile")
    breaks = [4, 6, 8, 10, 15, 25]
    style["vectorStyleStops"] = [{"value": v, "color": s["color"]}
                                 for v, s in zip(breaks, style["vectorStyleStops"])]
    m.add_geojson(fc(lines), name="Busiest air corridors (great circles)", strokeWidth=0.8,
                  opacity=0.75, **style,
                  popup=[{"field": "route", "label": "Route"}, {"field": "from", "label": "From"},
                         {"field": "to", "label": "To"},
                         {"field": "airline_routes", "label": "Airlines/routes on corridor"}],
                  tooltip=True)
    m.add_geojson(fc(hubs), name="Airport hubs (sized by routes)", fillColor="#fde68a",
                  strokeColor="#111827", strokeWidth=0.5, fillOpacity=0.9,
                  proportionalSizeEnabled=True, proportionalSizeProperty="routes",
                  proportionalSizeMinValue=0, proportionalSizeMaxValue=1000,
                  proportionalSizeMinRadius=1.2, proportionalSizeMaxRadius=7,
                  popup=[{"field": "airport", "label": "Airport"}, {"field": "city", "label": "City"},
                         {"field": "country", "label": "Country"}, {"field": "iata", "label": "IATA"},
                         {"field": "routes", "label": "Route count"}],
                  tooltip=True)
    m.set_layer_opacity("Busiest air corridors (great circles)", 0.8)
    map_legend(m, "Airline routes")
    save(m, "04_global_flight_network", "The Global Flight Network",
         "Human mobility: the 4,000 busiest airport-to-airport corridors from the OpenFlights "
         "route database, drawn as great circles and colored by the number of airline routes, "
         "with the 1,500 best-connected airports sized by route count.")


# ------------------------------------------------------------ 5. Citi Bike
def citibike():
    """Live Citi Bike station availability (GBFS)."""
    info = fetch_json("https://gbfs.citibikenyc.com/gbfs/en/station_information.json")
    status = fetch_json("https://gbfs.citibikenyc.com/gbfs/en/station_status.json")
    st = {s["station_id"]: s for s in status["data"]["stations"]}
    feats = []
    for s in info["data"]["stations"]:
        x = st.get(s["station_id"])
        if not x or not s.get("capacity"):
            continue
        bikes = x.get("num_bikes_available", 0)
        ebikes = x.get("num_ebikes_available", 0)
        feats.append(point(s["lon"], s["lat"], station=s["name"], capacity=s["capacity"],
                           bikes=bikes, ebikes=ebikes, docks=x.get("num_docks_available", 0),
                           pct_full=round(100 * bikes / s["capacity"], 1)))
    stamp = status.get("last_updated")
    m = Map(center=(-73.96, 40.74), zoom=11.8, basemap="positron")
    m.set_projection("mercator")
    style = build_choropleth_style([f["properties"]["pct_full"] for f in feats], "pct_full",
                                   class_count=5, colormap="rdylgn", scheme="equal-interval")
    style["vectorStyleStops"] = [
        {"value": 0, "color": "#d73027"}, {"value": 10, "color": "#fc8d59"},
        {"value": 30, "color": "#fee08b"}, {"value": 60, "color": "#91cf60"},
        {"value": 90, "color": "#1a9850"},
    ]
    m.add_geojson(fc(feats), name="Citi Bike stations (% of docks with a bike)",
                  strokeColor="#1f2937", strokeWidth=0.6, fillOpacity=0.9, **style,
                  proportionalSizeEnabled=True, proportionalSizeProperty="capacity",
                  proportionalSizeMinValue=10, proportionalSizeMaxValue=100,
                  proportionalSizeMinRadius=2.5, proportionalSizeMaxRadius=9,
                  popup=[{"field": "station", "label": "Station"},
                         {"field": "bikes", "label": "Bikes available"},
                         {"field": "ebikes", "label": "E-bikes available"},
                         {"field": "docks", "label": "Empty docks"},
                         {"field": "capacity", "label": "Capacity"},
                         {"field": "pct_full", "label": "Fill level", "suffix": " %", "kind": "number"}],
                  tooltip=True)
    map_legend(m, "Station fill level")
    save(m, "05_nyc_citibike_availability", "NYC Citi Bike Live Availability",
         f"Human mobility: a snapshot of all {len(feats):,} Citi Bike stations in New York City "
         f"(GBFS feed, epoch {stamp}), colored by how full each station is and sized by capacity. "
         "Morning/evening commutes empty Manhattan's residential edges and fill Midtown.")


# ---------------------------------------------------------- 6. Night lights
def night_lights():
    """VIIRS Black Marble 2012 vs 2016 swipe."""
    m = Map(center=(45, 28), zoom=3.2, basemap="dark")
    tpl = GIBS + "/VIIRS_Black_Marble/default/{y}-01-01/GoogleMapsCompatible_Level8/{{z}}/{{y}}/{{x}}.png"
    for y in (2012, 2016):
        m.add_tile_layer(tpl.format(y=y), name=f"Black Marble {y}", maxZoom=8,
                         attribution="NASA Earth Observatory / GIBS")
    m.split_map(left_layers=[m.find_layer("Black Marble 2012")],
                right_layers=[m.find_layer("Black Marble 2016")])
    save(m, "06_night_lights_2012_vs_2016", "Earth at Night: 2012 vs 2016",
         "Human footprint: NASA VIIRS Black Marble night lights, 2012 vs 2016 swipe. Look for "
         "the dimming of Syria and Yemen, and new light across India, the Gulf and "
         "North Dakota's oil fields.")


# ------------------------------------------------------------ 7. Forest loss
def forest_loss():
    """Hansen/UMD tree-cover loss 2001-2024 over Rondônia, Brazil."""
    m = Map(center=(-62.8, -10.2), zoom=6.6, basemap="positron")
    m.set_projection("mercator")
    m.add_tile_layer(ESRI_IMAGERY, name="Esri World Imagery", attribution=ESRI_ATTR)
    m.add_tile_layer(
        "https://storage.googleapis.com/earthenginepartners-hansen/tiles/gfc_v1.12/loss_year/{z}/{x}/{y}.png",
        name="Tree cover loss by year 2001–2024 (Hansen/UMD/GLAD)", maxZoom=12,
        blendMode="screen",
        attribution="Hansen et al. 2013, UMD/Google/USGS/NASA (GFC v1.12)")
    map_legend(m, "Forest loss", hide=["Esri World Imagery"], custom={
        "Tree cover loss by year 2001–2024 (Hansen/UMD/GLAD)": {
            "title": "Year of tree cover loss",
            "items": items({"2001": "#ffff00", "2008": "#ffbf00", "2016": "#ff7f00", "2024": "#ff0000"})}})
    save(m, "07_amazon_deforestation_rondonia", "Amazon Deforestation Frontier, Rondonia",
         "Environmental change: Global Forest Change v1.12 tree-cover loss over Rondônia, Brazil "
         "(the Amazon's 'fishbone' deforestation frontier), colored by year of loss 2001–2024 "
         "on Esri satellite imagery.")


# ------------------------------------------------------------ 8. Surface water
def surface_water():
    """JRC Global Surface Water, Aral Sea."""
    m = Map(center=(59.8, 45.0), zoom=6.3, basemap="positron")
    m.set_projection("mercator")
    m.add_tile_layer(ESRI_IMAGERY, name="Esri World Imagery", attribution=ESRI_ATTR)
    base = "https://storage.googleapis.com/global-surface-water/tiles2021/{k}/{{z}}/{{x}}/{{y}}.png"
    attr = "EC JRC / Google — Pekel et al. 2016"
    m.add_tile_layer(base.format(k="occurrence"), name="Water occurrence 1984–2021",
                     attribution=attr, maxZoom=13)
    m.add_tile_layer(base.format(k="transitions"), name="Water transitions 1984 → 2021",
                     attribution=attr, maxZoom=13)
    m.split_map(left_layers=[m.find_layer("Water occurrence 1984–2021")],
                right_layers=[m.find_layer("Water transitions 1984 → 2021")])
    map_legend(m, "Surface water", hide=["Esri World Imagery"], custom={
        "Water transitions 1984 → 2021": {"title": "Transitions 1984 → 2021 (right)", "items": items({
            "Permanent": "#0000ff", "New permanent": "#22b14c", "Lost permanent": "#d1102d",
            "Seasonal": "#99d9ea", "New seasonal": "#b5e61d", "Lost seasonal": "#e6a1aa",
            "Seasonal → permanent": "#ff7f27", "Permanent → seasonal": "#ffc90e",
            "Ephemeral permanent": "#7f7f7f", "Ephemeral seasonal": "#c3c3c3"})},
        "Water occurrence 1984–2021": {"title": "Occurrence 1984–2021 (left)", "items": items({
            "Rarely wet": "#ffcccc", "Wet half the time": "#8080e6", "Always wet": "#0000ff"})},
    })
    save(m, "08_aral_sea_surface_water_change", "The Vanishing Aral Sea",
         "Environmental change: the collapse of the Aral Sea in the JRC Global Surface Water "
         "record. Swipe between water occurrence (how often a pixel was wet, 1984–2021) and "
         "transitions (red = permanent water lost). Pan to Lake Mead, Lake Urmia or the "
         "Yangtze for more.")


# --------------------------------------------------------------- 9. CO2
def co2():
    """CO2 emissions per capita by country (Our World in Data), extruded."""
    rows = list(csv.DictReader(io.StringIO(fetch(
        "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv").decode())))
    latest = {}
    for r in rows:
        if r["iso_code"] and r["co2_per_capita"] and r["co2"]:
            y = int(r["year"])
            if y > latest.get(r["iso_code"], (0,))[0]:
                latest[r["iso_code"]] = (y, float(r["co2_per_capita"]), float(r["co2"]),
                                         float(r["share_global_co2"] or 0),
                                         float(r["cumulative_co2"] or 0))
    world = fetch_json("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
                       "geojson/ne_110m_admin_0_countries.geojson")
    feats = []
    for f in world["features"]:
        p = f["properties"]
        iso = p["ISO_A3"] if p["ISO_A3"] != "-99" else p["ADM0_A3"]
        if iso not in latest:
            continue
        y, pc, tot, share, cum = latest[iso]
        feats.append({"type": "Feature", "geometry": {"type": f["geometry"]["type"], "coordinates": round_coords(f["geometry"]["coordinates"])}, "properties": {
            "country": p["NAME"], "year": y, "co2_per_capita_t": round(pc, 2),
            "co2_total_mt": round(tot, 1), "share_global_pct": round(share, 2),
            "cumulative_co2_gt": round(cum / 1000, 1),
            "extrude_m": round(pc * 60000)}})
    m = Map(center=(20, 25), zoom=1.9, basemap="dark")
    m.set_pitch(45)
    m.set_projection("mercator")
    m.add_choropleth(
        fc(feats), "co2_per_capita_t", name="CO₂ per capita (t) — 3D", class_count=7,
        colormap="magma", scheme="quantile", fillOpacity=0.9, strokeColor="#111827",
        strokeWidth=0.3, extrusionEnabled=True, extrusionHeightProperty="extrude_m",
        extrusionHeightScale=1, extrusionOpacity=0.9,
        popup=[{"field": "country", "label": "Country"}, {"field": "year", "label": "Year"},
               {"field": "co2_per_capita_t", "label": "CO₂ per person", "suffix": " t", "kind": "number"},
               {"field": "co2_total_mt", "label": "Annual CO₂", "kind": "number", "thousands": True, "suffix": " Mt"},
               {"field": "share_global_pct", "label": "Share of world", "suffix": " %", "kind": "number"},
               {"field": "cumulative_co2_gt", "label": "Cumulative since 1750", "suffix": " Gt", "kind": "number"}],
        tooltip=True,
    )
    map_legend(m, "CO₂ per person")
    save(m, "09_co2_per_capita_3d", "CO2 Emissions per Person (3D)",
         "Climate change: annual fossil CO₂ emissions per person for every country (Our World "
         "in Data, Global Carbon Project; latest year), colored and extruded in 3D by per-capita "
         "emissions. Right-drag to tilt and rotate.")


# ------------------------------------------------------------ 10. Cyclones
def cyclones():
    """IBTrACS tropical cyclone tracks (last 3 years) over SST anomalies."""
    raw = fetch("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-"
                "stewardship-ibtracs/v04r01/access/csv/ibtracs.last3years.list.v04r01.csv").decode()
    reader = csv.DictReader(io.StringIO(raw))
    next(reader)  # units row
    tracks = defaultdict(list)
    for r in reader:
        try:
            lat, lon = float(r["LAT"]), float(r["LON"])
        except ValueError:
            continue
        w = r["USA_WIND"].strip() or r["WMO_WIND"].strip()
        wind = float(w) if w else 0.0
        tracks[r["SID"]].append((lon, lat, wind, r["NAME"].title(), r["SEASON"],
                                 r["BASIN"], r["ISO_TIME"][:10]))
    segs, peaks = [], []
    for sid, pts in tracks.items():
        vmax = max(p[2] for p in pts)
        if vmax < 34:
            continue
        name = pts[0][3] if pts[0][3] != "Unnamed" else f"Unnamed ({sid})"
        for a, b in zip(pts, pts[1:]):
            if abs(a[0] - b[0]) > 90:
                continue
            segs.append({"type": "Feature",
                         "geometry": {"type": "LineString", "coordinates": [[a[0], a[1]], [b[0], b[1]]]},
                         "properties": {"storm": name, "season": a[4], "basin": a[5],
                                        "date": a[6], "wind_kt": a[2], "peak_kt": vmax}})
        top = max(pts, key=lambda p: p[2])
        peaks.append(point(top[0], top[1], storm=name, season=top[4], date=top[6], peak_kt=vmax))
    segs.sort(key=lambda f: f["properties"]["wind_kt"])
    print(f"  cyclones: {len(peaks)} storms, {len(segs)} segments")
    stops = [{"value": 0, "color": "#5ebaff"}, {"value": 34, "color": "#00faf4"},
             {"value": 64, "color": "#ffffcc"}, {"value": 83, "color": "#ffe775"},
             {"value": 96, "color": "#ffc140"}, {"value": 113, "color": "#ff8f20"},
             {"value": 137, "color": "#ff6060"}]
    m = Map(center=(170, 15), zoom=1.7, basemap="dark")
    m.add_tile_layer(
        GIBS + "/GHRSST_L4_MUR25_Sea_Surface_Temperature_Anomalies/default/2026-09-25/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
        name="Sea surface temperature anomaly (2026-09-25)", maxZoom=6,
        attribution="NASA JPL GHRSST MUR25 / GIBS")
    m.set_layer_opacity("Sea surface temperature anomaly (2026-09-25)", 0.45)
    m.add_geojson(fc(segs), name="Cyclone tracks 2023–2026 (IBTrACS)", strokeWidth=2,
                  vectorStyleMode="graduated", vectorStyleProperty="wind_kt",
                  vectorStyleClassCount=len(stops), vectorStyleStops=stops,
                  popup=[{"field": "storm", "label": "Storm"}, {"field": "season", "label": "Season"},
                         {"field": "basin", "label": "Basin"}, {"field": "date", "label": "Date"},
                         {"field": "wind_kt", "label": "Wind", "suffix": " kt", "kind": "number"},
                         {"field": "peak_kt", "label": "Peak wind", "suffix": " kt", "kind": "number"}],
                  tooltip=True)
    m.add_geojson(fc(peaks), name="Peak intensity", minZoom=3, circleRadius=3,
                  fillColor="#ffffff", strokeColor="#000000", strokeWidth=0.5,
                  labels={"enabled": True, "field": "storm", "size": 11},
                  popup=[{"field": "storm", "label": "Storm"}, {"field": "season", "label": "Season"},
                         {"field": "date", "label": "Date"},
                         {"field": "peak_kt", "label": "Peak wind", "suffix": " kt", "kind": "number"}],
                  tooltip=True)
    m.set_layer_visibility("Peak intensity", True)
    map_legend(m, "Cyclones & SST", hide=["Peak intensity"], custom={
        "Cyclone tracks 2023–2026 (IBTrACS)": {"title": "Saffir–Simpson category", "items": items({
            "Tropical depression": "#5ebaff", "Tropical storm": "#00faf4", "Cat 1": "#ffffcc",
            "Cat 2": "#ffe775", "Cat 3": "#ffc140", "Cat 4": "#ff8f20", "Cat 5": "#ff6060"},
            shape="line")},
        "Sea surface temperature anomaly (2026-09-25)": {"title": "SST anomaly (°C)", "items": items({
            "≤ −3": "#6b00db", "−1.5": "#00aeff", "0": "#c2cab8", "+1.5": "#ffaa00",
            "≥ +3": "#88000f"})},
    })
    save(m, "10_tropical_cyclones_sst_anomaly", "Tropical Cyclones & Ocean Heat",
         "Climate hazards: every tropical cyclone of the last three seasons from NOAA IBTrACS, "
         "each track segment colored by Saffir–Simpson intensity, over the latest NASA MUR "
         "sea-surface-temperature anomaly.")


if __name__ == "__main__":
    import sys

    todo = sys.argv[1:] or ["asthma", "no2", "fires", "flights", "citibike", "night_lights",
                            "forest_loss", "surface_water", "co2", "cyclones"]
    for name in todo:
        print(name)
        globals()[name]()
