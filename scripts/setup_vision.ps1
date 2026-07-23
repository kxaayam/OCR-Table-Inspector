param(
    [string]$VenvPath = ".venv-vision"
)

$ErrorActionPreference = "Stop"
python -m venv $VenvPath
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"
& $PythonPath -m pip install --upgrade pip
& $PythonPath -m pip install -r requirements-vision.txt
Write-Host "Run: $PythonPath scripts/smoke_vision.py"
