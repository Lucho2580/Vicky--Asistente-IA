# build_msi.ps1
#
# Compila "Asistente IA - La Vianda" como ejecutable independiente
# (PyInstaller) y lo empaqueta en un instalador .msi (WiX Toolset v3).
#
# REQUISITOS (en tu máquina Windows):
#   1. Python 3.11+ instalado y en PATH.
#   2. WiX Toolset v3.11 o v3.14 instalado.
#      Descarga: https://wixtoolset.org/releases/
#      (o con chocolatey:  choco install wixtoolset -y)
#
# USO (desde la raíz del proyecto, en PowerShell):
#   .\packaging\build_msi.ps1
#
# Resultado: dist\AsistenteIA-Setup.msi

param(
    [string]$WixBinPath = "$env:ProgramFiles(x86)\WiX Toolset v3.14\bin"
)

$ErrorActionPreference = "Stop"

# Ubicarse en la raíz del proyecto (dos niveles arriba de este script).
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

Write-Host "== 1) Instalando dependencias Python ==" -ForegroundColor Cyan
pip install -r requirements.txt
pip install pyinstaller

Write-Host "== 2) Generando ejecutable con PyInstaller ==" -ForegroundColor Cyan
pyinstaller --noconfirm --clean packaging/pyinstaller/app.spec

if (-not (Test-Path "dist\AsistenteIA\AsistenteIA.exe")) {
    throw "No se generó dist\AsistenteIA\AsistenteIA.exe. Revisa la salida de PyInstaller arriba."
}

Write-Host "== 3) Buscando WiX Toolset (heat.exe / candle.exe / light.exe) ==" -ForegroundColor Cyan
$heat = Join-Path $WixBinPath "heat.exe"
$candle = Join-Path $WixBinPath "candle.exe"
$light = Join-Path $WixBinPath "light.exe"

foreach ($tool in @($heat, $candle, $light)) {
    if (-not (Test-Path $tool)) {
        throw "No se encontró $tool. Instala WiX Toolset v3 (https://wixtoolset.org/releases/) o pasa -WixBinPath a este script."
    }
}

$objDir = "packaging\wix\obj"
New-Item -ItemType Directory -Force -Path $objDir | Out-Null

Write-Host "== 4) Generando Files.wxs con heat.exe (harvesting de dist\AsistenteIA) ==" -ForegroundColor Cyan
& $heat dir "dist\AsistenteIA" -o "packaging\wix\Files.wxs" -ag -srd -cg AppFiles -dr INSTALLFOLDER -var var.SourceDir

Write-Host "== 5) Compilando con candle.exe ==" -ForegroundColor Cyan
& $candle -dSourceDir="dist\AsistenteIA" -out "$objDir\" "packaging\wix\Product.wxs" "packaging\wix\Files.wxs"

Write-Host "== 6) Enlazando con light.exe (genera el .msi final) ==" -ForegroundColor Cyan
& $light -ext WixUIExtension -sval -out "dist\AsistenteIA-Setup.msi" "$objDir\Product.wixobj" "$objDir\Files.wixobj"

Write-Host ""
Write-Host "Listo: dist\AsistenteIA-Setup.msi" -ForegroundColor Green
