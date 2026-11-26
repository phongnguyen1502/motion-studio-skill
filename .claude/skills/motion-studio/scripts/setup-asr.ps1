# setup-asr.ps1 — creates %USERPROFILE%\.motion-studio\asr-venv with faster-whisper for scripts\voice-timing.py.
# The Whisper model (~1.5 GB for "medium") downloads on first use and is cached in %USERPROFILE%\.cache.
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { throw 'Python 3.10+ is missing: winget install Python.Python.3.12' }
# short path outside the skill: survives reinstalls and avoids Windows' 260-char path limit
$venv = Join-Path $env:USERPROFILE '.motion-studio\asr-venv'
New-Item -ItemType Directory -Force (Split-Path $venv) | Out-Null
if (-not (Test-Path $venv)) { python -m venv $venv }
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet --upgrade pip
& (Join-Path $venv 'Scripts\python.exe') -m pip install --quiet faster-whisper "opencv-python-headless<5"
if ($LASTEXITCODE -ne 0) { throw 'pip install faster-whisper opencv failed' }
# person matte + face track for tao-video's speaker effects (text behind the person, halo, face lock…):
# MODNet (Apache-2.0, 25.9 MB) and YuNet (MIT, 0.23 MB), ONNX, run by the onnxruntime that faster-whisper installs
$models = Join-Path $env:USERPROFILE '.motion-studio\models'
New-Item -ItemType Directory -Force $models | Out-Null
$want = @(
  @('modnet.onnx', 'https://huggingface.co/Xenova/modnet/resolve/main/onnx/model.onnx', '07c308cf0fc7e6e8b2065a12ed7fc07e1de8febb7dc7839d7b7f15dd66584df9'),
  @('face_detection_yunet_2023mar.onnx', 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx', '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'))
# a blocked download only disables the speaker effects, so it warns instead of failing the whole setup;
# offline: copy the two .onnx files into %USERPROFILE%\.motion-studio\models beforehand (the company kit does)
foreach ($m in $want) {
  $f = Join-Path $models $m[0]
  try {
    if (-not (Test-Path $f)) { Invoke-WebRequest -Uri $m[1] -OutFile $f -UseBasicParsing }
    if ((Get-FileHash $f -Algorithm SHA256).Hash.ToLower() -ne $m[2]) { Remove-Item $f; throw "checksum mismatch" }
  } catch { Write-Warning "Model $($m[0]) not installed ($($_.Exception.Message)): talking-head speaker effects stay off." }
}
Write-Host "ASR ready: $venv\Scripts\python.exe $dir\voice-timing.py <voice> <script.txt> <timing.json>"
