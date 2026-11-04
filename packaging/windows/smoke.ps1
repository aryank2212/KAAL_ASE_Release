# Smoke test for a built KAAL ASE executable. Usage: smoke.ps1 -Exe <path> [-Port 8150]
param([Parameter(Mandatory)][string]$Exe, [int]$Port = 8150)
$ErrorActionPreference = "Stop"
$env:KAAL_NO_OPEN = "1"
$data = Join-Path $env:RUNNER_TEMP ("kaal-smoke-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
$p = Start-Process -FilePath $Exe -ArgumentList @("--data-dir", $data, "--port", $Port, "--host", "127.0.0.1") -PassThru -WindowStyle Hidden `
     -RedirectStandardOutput "$data.out.log" -RedirectStandardError "$data.err.log"
try {
  $ok = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    try { if ((Invoke-RestMethod "http://127.0.0.1:$Port/health").status -eq "ok") { $ok = $true; break } } catch {}
    if ($p.HasExited) { break }
  }
  if (-not $ok) {
    $log = (Get-Content "$data.out.log", "$data.err.log" -ErrorAction SilentlyContinue | Select-Object -Last 40 | Out-String)
    $tail = $log.Substring([Math]::Max(0, $log.Length - 1800)) -replace "`r", "" -replace "`n", "%0A"
    Write-Host "::error title=server did not become healthy::$tail"
    throw "server did not become healthy"
  }
  $key = (Get-Content (Join-Path $data "api_key")).Trim()
  $h = @{ "X-API-Key" = $key }
  $ui = Invoke-WebRequest "http://127.0.0.1:$Port/ui/" -UseBasicParsing
  if ($ui.StatusCode -ne 200 -or $ui.Content -notmatch "KAAL ASE Console") { throw "console page missing" }
  try { Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/system" | Out-Null; throw "API answered without a key" } catch { if ($_.Exception.Message -eq "API answered without a key") { throw } }
  $sys = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/system" -Headers $h
  Write-Host "version $($sys.version); connectors: ready=$($sys.connectors.ready) needs_setup=$($sys.connectors.needs_setup) not_installed=$($sys.connectors.not_installed)"
  if ($sys.connectors.ready -lt 8) { throw "too few connectors ready" }
  $names = (Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/osint/connectors" -Headers $h) | Where-Object { $_.status -eq "ready" } | ForEach-Object { $_.name }
  Write-Host ("ready: " + ($names -join ", "))
  # face_* connectors need the opt-in model download, Holehe/GHunt are opt-in tools, aisstream needs a key: none of those are required here
  foreach ($need in @("dns_records", "whois", "wayback", "phone_parse", "image_metadata", "maigret", "sherlock", "sentinel2", "opensky", "wikipedia_briefing")) { if ($names -notcontains $need) { throw "connector not ready: $need" } }
  $case = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/cases" -Method Post -Headers $h -ContentType "application/json" -Body '{"title":"smoke"}'
  $body = '{"connector":"dns_records","target":"example.com","purpose":"Installer smoke test on a public domain"}'
  $r = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/cases/$($case.case_id)/osint/run" -Method Post -Headers $h -ContentType "application/json" -Body $body
  if (-not $r.requires_human_review) { throw "contract broken" }
  $ph = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/cases/$($case.case_id)/osint/run" -Method Post -Headers $h -ContentType "application/json" -Body '{"connector":"phone_parse","target":"+14155552671","purpose":"Installer smoke test, offline parsing"}'
  if ($ph.outputs.region -ne "US") { throw "phone_parse (bundled data) failed" }
  # Real imagery read through GDAL/rasterio inside the frozen app. Network-dependent, so a failure here is a warning, not fatal.
  try {
    $s2 = Invoke-RestMethod "http://127.0.0.1:$Port/api/v1/cases/$($case.case_id)/osint/run" -Method Post -Headers $h -ContentType "application/json" -TimeoutSec 180 `
      -Body '{"connector":"sentinel2","target":"72.85,18.90,72.92,18.96","purpose":"Installer smoke test of the imagery pipeline on public open data"}'
    Write-Host "sentinel2 OK: scene $($s2.outputs.scene_id), $($s2.outputs.size[0])x$($s2.outputs.size[1]) px, $($s2.outputs.detections.Count) candidates"
  } catch { Write-Host "::warning title=sentinel2 in frozen build::$($_.Exception.Message) $($_.ErrorDetails.Message)" }
  Write-Host "smoke test passed"
} catch {
  Write-Host "::error title=smoke test failed::$($_.Exception.Message)"
  throw
} finally {
  if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
}
