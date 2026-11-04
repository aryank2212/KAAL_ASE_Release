#!/bin/sh
# Installs the optional OSINT tools into isolated venvs under $KAAL_TOOLS_DIR (default ~/.kaal/tools).
# Holehe (GPL-3.0) and GHunt (AGPL-3.0) run as separate programs and are never imported by KAAL.
# Face models are pinned by SHA-256 in app/connectors/sensitive.py and re-checked at load time.
set -eu
T="${KAAL_TOOLS_DIR:-$HOME/.kaal/tools}"
mkdir -p "$T/models"
for tool in holehe ghunt; do
  [ -x "$T/$tool-venv/bin/$tool" ] && { echo "$tool: already installed"; continue; }
  python3 -m venv "$T/$tool-venv"
  nice -n 15 "$T/$tool-venv/bin/pip" install -q --disable-pip-version-check "$tool"
  echo "$tool: installed"
done
# theHarvester (GPL-2.0) runs as a separate program. 4.x needs Python 3.14, which uv downloads itself (https://docs.astral.sh/uv/).
if command -v uv >/dev/null 2>&1; then
  if [ -x "$T/theharvester-venv/bin/theHarvester" ]; then echo "theHarvester: already installed"; else
    rm -rf "$T/theharvester-src"
    git clone -q --depth 1 --branch 4.11.1 https://github.com/laramies/theHarvester.git "$T/theharvester-src"
    UV_PROJECT_ENVIRONMENT="$T/theharvester-venv" nice -n 15 uv sync --project "$T/theharvester-src" --frozen --no-dev --python 3.14 >/dev/null
    echo "theHarvester: installed (4.11.1, from its lockfile)"
  fi
else
  echo "theHarvester: skipped (needs uv: https://docs.astral.sh/uv/getting-started/installation/)"
fi
base=https://github.com/opencv/opencv_zoo/raw/main/models
[ -f "$T/models/face_detection_yunet_2023mar.onnx" ]   || curl -fsSL -o "$T/models/face_detection_yunet_2023mar.onnx"   "$base/face_detection_yunet/face_detection_yunet_2023mar.onnx"
[ -f "$T/models/face_recognition_sface_2021dec.onnx" ] || curl -fsSL -o "$T/models/face_recognition_sface_2021dec.onnx" "$base/face_recognition_sface/face_recognition_sface_2021dec.onnx"
echo "Face models in $T/models (checksum is verified when first used)."
echo "GHunt still needs ONE manual step as the service user:  $T/ghunt-venv/bin/ghunt login"
