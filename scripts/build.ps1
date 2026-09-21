# Genera dist\TINT_SIS\TINT_SIS.exe y, si Inno Setup 6 esta instalado, dist\installer\TINT_SIS_Setup_<version>.exe
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 [-SkipTests]
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "No se encontro $Python. Crea el venv e instala requirements.txt primero." }

function Invoke-Step([string]$Title, [scriptblock]$Block) {
    Write-Host "`n==> $Title" -ForegroundColor Cyan
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "Fallo: $Title (codigo $LASTEXITCODE)" }
}

$Version = (Select-String -Path "src\tint_sis\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
Write-Host "TINT_SIS version $Version"

Invoke-Step "Instalando dependencias de build" { & $Python -m pip install -q -r requirements.txt -r requirements-build.txt }

if (-not $SkipTests) {
    Invoke-Step "Corriendo tests" { & $Python -m pytest -q tests }
}

$Ico = Join-Path $Root "assets\tint_sis.ico"
$Png = Join-Path $Root "assets\logo.png"
if (-not (Test-Path $Ico) -and (Test-Path $Png)) {
    Invoke-Step "Convirtiendo assets\logo.png a assets\tint_sis.ico" {
        & $Python -c "from PIL import Image; Image.open(r'$Png').convert('RGBA').save(r'$Ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    }
}
if (-not (Test-Path $Ico)) { Write-Warning "Sin icono: agrega assets\logo.png o assets\tint_sis.ico para usar el logo." }

Invoke-Step "Empaquetando con PyInstaller" { & $Python -m PyInstaller packaging\tint_sis.spec --noconfirm --clean }
Write-Host "Ejecutable: $Root\dist\TINT_SIS\TINT_SIS.exe" -ForegroundColor Green

$Redist = Join-Path $Root "packaging\redist\MicrosoftEdgeWebview2Setup.exe"
if (-not (Test-Path $Redist)) {
    Write-Host "`n==> Descargando bootstrapper de WebView2" -ForegroundColor Cyan
    New-Item -ItemType Directory -Force (Split-Path $Redist) | Out-Null
    try {
        Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile $Redist -UseBasicParsing
    } catch {
        Write-Warning "No se pudo descargar WebView2 ($_). El instalador se generara sin el; los equipos sin WebView2 deberan instalarlo aparte."
    }
}

$Iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($Iscc) {
    Invoke-Step "Compilando instalador" { & $Iscc "/DAppVersion=$Version" "packaging\installer.iss" }
    Write-Host "Instalador: $Root\dist\installer\TINT_SIS_Setup_$Version.exe" -ForegroundColor Green
} else {
    Write-Warning "Inno Setup 6 no esta instalado: solo se genero la carpeta dist\TINT_SIS. Instalalo con 'winget install JRSoftware.InnoSetup' y vuelve a correr el script."
}
