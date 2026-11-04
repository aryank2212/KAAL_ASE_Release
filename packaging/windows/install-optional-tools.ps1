# Optional extras for Windows: Holehe, GHunt (separate Python environments) and the face models.
# Needs Python 3.10+ on PATH. Run in PowerShell:  .\install-optional-tools.ps1
$ErrorActionPreference = "Stop"
$t = if ($env:KAAL_TOOLS_DIR) { $env:KAAL_TOOLS_DIR } else { Join-Path $env:APPDATA "KAAL-ASE\tools" }
New-Item -ItemType Directory -Force -Path "$t\models" | Out-Null
foreach ($tool in "holehe", "ghunt") {
  if (-not (Test-Path "$t\$tool-venv\Scripts\$tool.exe")) { python -m venv "$t\$tool-venv"; & "$t\$tool-venv\Scripts\pip.exe" install -q $tool; Write-Host "$tool installed" }
}
$base = "https://github.com/opencv/opencv_zoo/raw/main/models"
foreach ($m in @(@("face_detection_yunet", "face_detection_yunet_2023mar.onnx"), @("face_recognition_sface", "face_recognition_sface_2021dec.onnx"))) {
  $dest = "$t\models\$($m[1])"; if (-not (Test-Path $dest)) { Invoke-WebRequest "$base/$($m[0])/$($m[1])" -OutFile $dest -UseBasicParsing }
}
Write-Host "Set KAAL_TOOLS_DIR=$t before starting KAAL ASE. GHunt still needs one manual step:  $t\ghunt-venv\Scripts\ghunt.exe login"
