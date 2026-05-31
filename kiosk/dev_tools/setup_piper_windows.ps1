$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$piperRoot = Join-Path $root "kiosk\models\piper"
$archivePath = Join-Path $piperRoot "piper_windows_amd64.zip"
$extractPath = Join-Path $piperRoot "extract"
$binPath = Join-Path $piperRoot "bin"
$voicePath = Join-Path $piperRoot "voices"

$piperUrl = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
$voiceUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx?download=true"
$voiceConfigUrl = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json?download=true"

New-Item -ItemType Directory -Force -Path $piperRoot, $extractPath, $binPath, $voicePath | Out-Null

if (-not (Test-Path (Join-Path $binPath "piper.exe"))) {
    Write-Host "Downloading Piper for Windows..."
    Invoke-WebRequest -Uri $piperUrl -OutFile $archivePath

    Write-Host "Extracting Piper..."
    Expand-Archive -Path $archivePath -DestinationPath $extractPath -Force
    $piperExe = Get-ChildItem -Path $extractPath -Recurse -Filter "piper.exe" | Select-Object -First 1
    if ($null -eq $piperExe) {
        throw "piper.exe was not found in the downloaded archive."
    }

    Copy-Item -Path (Join-Path $piperExe.DirectoryName "*") -Destination $binPath -Recurse -Force
}

if (-not (Test-Path (Join-Path $voicePath "en_US-amy-medium.onnx"))) {
    Write-Host "Downloading Amy medium voice..."
    Invoke-WebRequest -Uri $voiceUrl -OutFile (Join-Path $voicePath "en_US-amy-medium.onnx")
}

if (-not (Test-Path (Join-Path $voicePath "en_US-amy-medium.onnx.json"))) {
    Write-Host "Downloading Amy medium voice config..."
    Invoke-WebRequest -Uri $voiceConfigUrl -OutFile (Join-Path $voicePath "en_US-amy-medium.onnx.json")
}

Remove-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $extractPath -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "Piper is ready:"
Write-Host "  kiosk/models/piper/bin/piper.exe"
Write-Host "  kiosk/models/piper/voices/en_US-amy-medium.onnx"
