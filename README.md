# geolibre-assets

Static assets for [GeoLibre](https://github.com/opengeos/GeoLibre), published via GitHub Pages at
**<https://assets.geolibre.app>**.

Any file committed to `main` is served at the matching path:

```
repo:   images/logo.png
url:    https://assets.geolibre.app/images/logo.png
```

## Layout

| Directory | Contents                                       |
| --------- | ---------------------------------------------- |
| `data/`   | Sample datasets (GeoJSON, PMTiles, CSV, Parquet) |
| `images/` | Images, logos, icons, screenshots               |
| `styles/` | MapLibre style JSON and sprite/glyph resources  |
| `fonts/`  | Font glyph PBFs                                 |

## Adding files

```bash
git clone https://github.com/opengeos/geolibre-assets.git
cd geolibre-assets
cp /path/to/file images/
git add images/file
git commit -m "Add file"
git push
```

Deployment runs automatically on push to `main` and usually completes within a minute.

## Notes

- Keep individual files under **100 MB** (GitHub's hard limit); the published
  site must stay under **1 GB**, and Pages has a soft bandwidth limit of
  100 GB/month.
- Prefer optimized formats: PMTiles for tiles, WebP/AVIF for images,
  GeoParquet for tabular data.
- `.nojekyll` is present so files and directories beginning with `_` are served
  as-is.
- Responses are served with permissive CORS, so assets can be fetched
  cross-origin from any GeoLibre app.
- Files here are public and cached by GitHub's CDN. Do not commit anything
  secret, and treat published paths as permanent — renaming a file breaks
  anything already pointing at it.

## License

Code and configuration in this repository are released under the [MIT License](LICENSE).
Individual datasets may carry their own licenses; see the accompanying
`README` or `LICENSE` file within each directory where applicable.
