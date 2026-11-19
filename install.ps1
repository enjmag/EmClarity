# EmClarity installer. Run via install.bat (or: powershell -ExecutionPolicy Bypass -File install.ps1)
# Everything lands inside this folder: .venv, envs\, bin\, models\.
param(
    [switch]$WithResemble,   # also build the optional Resemble Enhance environment
    [switch]$SkipModels      # skip pre-downloading model weights
)
# 'Continue' because Windows PowerShell 5.1 turns native stderr into terminating errors under 'Stop'.
# Every native call is checked through $LASTEXITCODE instead.
$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location $Root

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------- uv
Step "Checking Python and uv"
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { throw "Python 3.10+ is required. Install it from https://www.python.org/downloads/ and tick 'Add to PATH'." }
& python -m uv --version 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing uv (fast Python package manager)..."
    & python -m pip install --user --quiet uv
    if ($LASTEXITCODE -ne 0) { throw "Could not install uv." }
}
function UV { & python -m uv @args; if ($LASTEXITCODE -ne 0) { throw "uv $args failed" } }

# ---------------------------------------------------------------- main env
$env:UV_CACHE_DIR = Join-Path $Root '.uv-cache'
Step "Creating main environment (.venv, Python 3.12)"
if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) { UV venv .venv --python 3.12 }
$VPy = "$Root\.venv\Scripts\python.exe"

Step "Installing PyTorch 2.8 with CUDA 12.8 (large download, one time)"
UV pip install --python $VPy torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu128

Step "Installing EmClarity dependencies"
UV pip install --python $VPy -r requirements.txt

# ---------------------------------------------------------------- DeepFilterNet binary
Step "Fetching DeepFilterNet 3 (standalone binary)"
New-Item -ItemType Directory -Force "$Root\bin" | Out-Null
$df = "$Root\bin\deep-filter.exe"
if (-not (Test-Path $df)) {
    $url = 'https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-x86_64-pc-windows-msvc.exe'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $df -UseBasicParsing -ErrorAction Stop
}

# ---------------------------------------------------------------- optional Resemble Enhance env
if ($WithResemble) {
    Step "Creating optional Resemble Enhance environment (envs\resemble, Python 3.11, torch 2.1.1)"
    if (-not (Test-Path "$Root\envs\resemble\Scripts\python.exe")) { UV venv envs\resemble --python 3.11 }
    $RPy = "$Root\envs\resemble\Scripts\python.exe"
    UV pip install --python $RPy torch==2.1.1 torchaudio==2.1.1 --index-url https://download.pytorch.org/whl/cu118
    # Install without deepspeed (training-only, does not build on Windows); a stub is provided by EmClarity.
    UV pip install --python $RPy --no-deps resemble-enhance==0.0.1
    UV pip install --python $RPy "numpy==1.26.2" "librosa==0.10.1" "omegaconf==2.3.0" "soundfile==0.12.1" "scipy==1.11.4" "tqdm" "rich" "resampy==0.4.2" "matplotlib" "celluloid" "pandas" "tabulate" "ptflops" "huggingface_hub"
    if (-not $SkipModels) {
        $env:EMCLARITY_RESEMBLE_RUN_DIR = Join-Path $Root 'models\resemble'
        & $RPy "$Root\emclarity\engines\_resemble_runner.py" --fetch
        if ($LASTEXITCODE -ne 0) { throw "Resemble Enhance weight download failed." }
    }
}

# ---------------------------------------------------------------- models
if (-not $SkipModels) {
    Step "Downloading model weights into models\ (Sidon, w2v-BERT, Demucs)"
    $env:HF_HOME = Join-Path $Root 'models\hf'
    $env:TORCH_HOME = Join-Path $Root 'models\torch'
    & $VPy -m emclarity.fetch_models
    if ($LASTEXITCODE -ne 0) { throw "Model download failed." }
}

Step "Clearing the download cache (frees ~10+ GB; installed files are unaffected)"
& python -m uv cache clean 2>&1 | Out-Null

Step "Done. Drag audio or video files (or a folder) onto Enhance.bat."
