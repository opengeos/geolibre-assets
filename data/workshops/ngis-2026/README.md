# NGIS 2026 GeoLibre workshop data

Datasets for the full-day workshop "Cloud-Native GIS with GeoLibre" (NGIS 2026
preconference, Reno, November 17, 2026). Teaching materials:
<https://geolibre.app/workshops/ngis-2026/>.

Served at `https://assets.geolibre.app/data/workshops/ngis-2026/<file>`.

| File | Format | Features / size | Source |
| --- | --- | --- | --- |
| `nv_counties.geojson` | GeoJSON | 17 Nevada counties | US Census Bureau, 2023 cartographic boundary (1:500k) |
| `us_states.geojson` | GeoJSON (simplified) | 56 states and territories | US Census Bureau, 2023 cartographic boundary (1:500k) |
| `us_counties.fgb` | FlatGeobuf | 3,235 counties | US Census Bureau, 2023 cartographic boundary (1:500k) |
| `us_counties.parquet` | GeoParquet 1.1 (bbox-sorted, covering bbox, 256-row groups, ZSTD) | 3,235 counties | same as above |
| `us_counties.pmtiles` | PMTiles vector tiles, z0-10, layer `counties` | 3,235 counties | same as above |
| `nv_earthquakes.csv` | CSV (longitude/latitude) | 8,031 events, M2.5+, 2016-2025 | USGS ANSS ComCat (FDSN event service) |
| `nv_earthquakes.parquet` | GeoParquet points | 8,031 events | same as above |
| `reno_tahoe_dem.tif` | Cloud-Optimized GeoTIFF, Float32, ~1 arc-second (~30 m), meters | 2520 x 3240, 13 MB | USGS 3DEP 1/3 arc-second DEM tile n40w120, resampled (average) |
| `reno_sites.geojson` | GeoJSON points | 8 Reno-Tahoe landmarks | Hand-digitized, approximate coordinates (workshop use only) |

The earthquake query covered latitude 35 to 42.1 and longitude -120.1 to -114
(Nevada and its edges), magnitude 2.5 and above, January 1, 2016 to
January 1, 2026, events of type `earthquake` only. The DEM covers longitude
-120.25 to -119.55 and latitude 38.85 to 39.75 (Reno, Carson City, Lake Tahoe).

US Census Bureau and USGS data are US Government works in the public domain.
