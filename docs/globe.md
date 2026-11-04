# Globe: God's Eye View inside the console

The console's **Globe** tab embeds [God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) (MIT, by Bilawal Sidhu), a 3D
globe with live aircraft, ships, satellites, quakes, weather and public cameras. KAAL passes your Area-watch bounding box as the
camera position (**Fly to area**), and Area watch has an **Open in Globe** button.

It is a **separate project** with its own release cycle, so it is not bundled in the installers. It runs as a companion service.

## Install

Needs Docker. The script clones a pinned, reviewed commit, builds the image (Node 24, pinned by the project), and publishes it
only on the address you give:

    GEV_BIND=100.64.0.1 \
    KAAL_CONSOLE_ORIGIN=http://100.64.0.1:8140 \
    GEV_ALLOWED_HOSTS=my-server.tailnet.ts.net \
    scripts/install-globe.sh

Then tell KAAL where it is and restart:

    KAAL_GLOBE_URL=http://100.64.0.1:4173     # in /etc/kaal-ase/kaal-ase.env or your service environment

Builds on small or fragile machines: set `GEV_BUILD_ARGS` (default `--memory 4g --memory-swap 4g`; add `--cpuset-cpus 0-3` to cap CPUs).

## After a reboot

The globe publishes on a private address (for example the Tailscale one), and Docker does not retry a container that failed to bind at
boot. If the Globe tab says "unreachable" after a restart, start it again:

    docker compose -f ~/gods-eye-view/compose.kaal.yaml up -d

If you want it to start by itself, add a systemd unit that waits for the private address before running that command. The installer does
not create one, because it installs nothing that starts at boot without you choosing it.

## Security: read this

The globe app is a development server that brokers any provider keys you give it. Its own docs say it is "not a hardened production
service". So:

- Publish it only on loopback or a private network (for example Tailscale), never `0.0.0.0` on a shared network or the internet.
- The script sets `GEV_KEY_SETUP_TRUSTED_PEERS=none` (required by the project when published beyond loopback) and
  `GEV_EMBED_FRAME_ANCESTORS` so **only** your KAAL console origin may frame it.
- KAAL's own content-security-policy allows framing only the address in `KAAL_GLOBE_URL`, and KAAL itself cannot be framed by others.
- Anyone who can reach the globe can use whatever keys are saved in it. Keep keys out of it, or keep access private.

## Sharing keys

Both apps read `AISSTREAM_API_KEY` and `OPENSKY_CLIENT_ID` / `OPENSKY_CLIENT_SECRET`. Set them in each app's own environment; they
are not shared automatically.

## Honest limits

- Rendering the 3D globe needs a real GPU in your browser. Software rendering (a headless browser on a small server) pegs the CPU and
  can overheat a fragile machine: open the Globe tab from your laptop or phone, not from a browser running on the server itself.
- Some globe layers are estimates (the project says CCTV poses and launch trajectories are coarse; traffic is simulated). Treat
  anything seen there as a lead and record it in a case before relying on it.
- Some bundled data is non-commercial (see the project's `DATA_SOURCES.md`). Photorealistic 3D needs your own Cesium ion token or
  Google Maps key, under their terms.
- The integration is a frame plus deep links. Tracked targets in the globe are not automatically saved as KAAL evidence.
