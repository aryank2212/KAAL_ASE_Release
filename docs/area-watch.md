# Area watch: Sentinel-2, OpenSky and aisstream

The console's **Area watch** tab and the `sentinel2`, `opensky` and `aisstream` connectors take a bounding box
(`west,south,east,north` in decimal degrees) and put results on a map. Everything saved is proposed evidence with an
audit event, like any other connector.

| Connector | Source | Key needed | Limits |
|---|---|---|---|
| `sentinel2` | Copernicus Sentinel-2 L2A via the Earth Search STAC (open data on AWS) | none | box up to 0.6 degrees per side; latest scene under 40% cloud, usually 1 to 5 days old |
| `opensky` | OpenSky Network REST API | optional (`OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`) | box up to 10 degrees; anonymous access is rate limited |
| `aisstream` | aisstream.io live AIS websocket | free key in `AISSTREAM_API_KEY` | box up to 6 degrees; samples about 12 seconds of the stream |

Imagery is credited as "Contains modified Copernicus Sentinel data"; the map is credited to OpenStreetMap contributors.

## What the detector can and cannot do (please read)

The `sentinel2` connector runs a detector over the downloaded tile. **It does not use the KAAL model by default.**

- Sentinel-2 is 10 metres per pixel. A vehicle is smaller than one pixel, so the published KAAL model (trained on
  ground-vehicle photos) cannot detect vehicles here. Large ships are a few pixels long and can be seen.
- The built-in detector is a classical baseline: it finds large smooth water areas, then flags small bright or dark
  outliers inside them. On a real scene over Mumbai Harbour it found 158 candidates, and a manual zoom showed an anchorage
  of ships being picked up correctly. It was **not benchmarked** against ground truth: expect misses (small or low-contrast
  vessels) and false positives (wakes, surf, buoys). Results are labelled as candidates.
- `KAAL_DETECTOR=rfdetr` with `KAAL_RFDETR_WEIGHTS=<checkpoint>` plugs in an RF-DETR checkpoint instead. That adapter is
  **untested** in this release and only makes sense with a model trained on imagery of the right resolution.

ADS-B and AIS are incomplete and AIS is self-reported (it can be switched off or spoofed). Treat the layers as leads.
