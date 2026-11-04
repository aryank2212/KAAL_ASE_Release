#!/bin/sh
# Installs God's Eye View (MIT, https://github.com/bilawalsidhu/gods-eye-view) as a companion service for the KAAL ASE console.
# It runs in Docker (Node 24 image pinned by the project) from a pinned commit, published ONLY on the address you choose.
#
#   GEV_BIND=100.64.0.1 KAAL_CONSOLE_ORIGIN=http://100.64.0.1:8140 scripts/install-globe.sh
#
# Then set KAAL_GLOBE_URL=http://<GEV_BIND>:<GEV_PORT> for KAAL ASE and restart it.
set -eu
GEV_COMMIT="${GEV_COMMIT:-ac28a11e41d426075f22a58193b6e8755c8df0eb}"          # reviewed commit; change deliberately
DIR="${GEV_DIR:-$HOME/gods-eye-view}"
BIND="${GEV_BIND:-127.0.0.1}"                                                   # address to publish on. Never 0.0.0.0 on a shared network.
PORT="${GEV_PORT:-4173}"
KAAL_ORIGIN="${KAAL_CONSOLE_ORIGIN:-http://127.0.0.1:8140}"                    # the only page allowed to frame the globe
ALLOWED_HOSTS="${GEV_ALLOWED_HOSTS:-}"                                          # extra Host names (IPs and localhost always work)
BUILD_ARGS="${GEV_BUILD_ARGS:---memory 4g --memory-swap 4g}"                    # keep builds from exhausting a small server
command -v docker >/dev/null || { echo "Docker is required." >&2; exit 1; }
[ -d "$DIR/.git" ] || git clone -q https://github.com/bilawalsidhu/gods-eye-view.git "$DIR"
if [ "$(git -C "$DIR" rev-parse HEAD)" != "$GEV_COMMIT" ]; then
  git -C "$DIR" fetch -q --depth 1 origin "$GEV_COMMIT" && git -C "$DIR" checkout -q "$GEV_COMMIT"
fi
TAG="$(printf %.7s "$GEV_COMMIT")"
if ! docker image inspect "gods-eye-view:$TAG" >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  nice -n 15 docker build $BUILD_ARGS -t "gods-eye-view:$TAG" "$DIR"
fi
cat > "$DIR/compose.kaal.yaml" <<YML
name: kaal-globe
services:
  gods-eye-view:
    image: gods-eye-view:$TAG
    user: "$(id -u):$(id -g)"
    restart: unless-stopped
    environment:
      GEV_KEY_SETUP_TRUSTED_PEERS: none          # required when published beyond loopback (project README)
      GEV_EMBED_FRAME_ANCESTORS: "$KAAL_ORIGIN"
      GEV_ALLOWED_HOSTS: "$ALLOWED_HOSTS"
    ports:
      - "$BIND:$PORT:4173"
    volumes:
      - .:/app:z
      - /app/node_modules
    mem_limit: 2g
    cpus: 2
YML
docker compose -f "$DIR/compose.kaal.yaml" up -d
echo "God's Eye View is up at http://$BIND:$PORT  (framable only by $KAAL_ORIGIN)"
echo "Next: set KAAL_GLOBE_URL=http://$BIND:$PORT for KAAL ASE and restart it."
