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
base=https://github.com/opencv/opencv_zoo/raw/main/models
[ -f "$T/models/face_detection_yunet_2023mar.onnx" ]   || curl -fsSL -o "$T/models/face_detection_yunet_2023mar.onnx"   "$base/face_detection_yunet/face_detection_yunet_2023mar.onnx"
[ -f "$T/models/face_recognition_sface_2021dec.onnx" ] || curl -fsSL -o "$T/models/face_recognition_sface_2021dec.onnx" "$base/face_recognition_sface/face_recognition_sface_2021dec.onnx"
echo "Face models in $T/models (checksum is verified when first used)."
echo "GHunt still needs ONE manual step as the service user:  $T/ghunt-venv/bin/ghunt login"
