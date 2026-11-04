# KAAL ASE 2.2.0

**Installers** (assets below): `kaal-ase_2.2.0_all.deb` (Debian/Ubuntu), `kaal-ase-2.2.0-1-any.pkg.tar.zst` (Arch),
`KAAL-ASE-2.2.0-setup.exe` (Windows), `kaal-model.py` (change the model from any machine), `SHA256SUMS.txt`.
How to install: docs/installing.md.

## New
- **Web console** at `/ui/`: overview, investigate (run connectors, accept or reject findings), area-watch map, model settings, audit trail.
- **Remote models**: run the API on a server and the models on your laptop with Ollama or LM Studio; switch provider and model live.
- **Sentinel-2 + OpenSky + aisstream** on one map. ExifTool for far richer image metadata.
- Installers for Debian/Ubuntu, Arch and Windows, each smoke-tested in CI before release.

## Read before relying on it
- The satellite detector is a **baseline heuristic**, not the KAAL model, and was not benchmarked. Sentinel-2 cannot resolve vehicles. See docs/area-watch.md.
- The Windows installer is **not code-signed**: SmartScreen will warn. Verify with `SHA256SUMS.txt`.
- Holehe returned mostly rate-limit failures from the test server; it reports that as an error, not as "no results". GHunt needs your own `ghunt login`.
- The RF-DETR adapter and theHarvester adapter are untested here. This repository has no LICENSE file yet.
- Use only for lawful, authorized research. Every result is an unverified lead until an analyst accepts it.
