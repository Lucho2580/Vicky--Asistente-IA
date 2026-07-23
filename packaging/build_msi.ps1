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

if (Test-Path ".env") {
    Write-Host "== 2.1) Incluyendo .env del proyecto en el instalador ==" -ForegroundColor Cyan
    Copy-Item ".env" "dist\AsistenteIA\.env" -Force
} else {
    Write-Host "== 2.1) No hay .env en la raíz del proyecto: el instalador quedará sin credenciales precargadas ==" -ForegroundColor Yellow
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

# La versión del .msi sale de core/version.py (única fuente de verdad).
# En un build local no hay tag de git, así que se usa lo que ya esté
# escrito ahí (por defecto, o lo que haya dejado un build anterior de CI).
$versionContent = Get-Content "core\version.py" -Raw
$appVersion = if ($versionContent -match 'APP_VERSION\s*=\s*"([^"]+)"') { $matches[1] } else { "0.0.0" }
$appBuild = if ($versionContent -match 'APP_BUILD\s*=\s*(\d+)') { $matches[1] } else { "0" }
$productVersion = "$appVersion.$appBuild"
Write-Host "Version del .msi: $productVersion (desde core/version.py)" -ForegroundColor Cyan

$objDir = "packaging\wix\obj"
New-Item -ItemType Directory -Force -Path $objDir | Out-Null

Write-Host "== 4) Generando Files.wxs con heat.exe (harvesting de dist\AsistenteIA) ==" -ForegroundColor Cyan
& $heat dir "dist\AsistenteIA" -o "packaging\wix\Files.wxs" -ag -srd -cg AppFiles -dr INSTALLFOLDER -var var.SourceDir

# La version se sustituye DIRECTO en una copia del .wxs (no se pasa por
# -d de candle.exe: esa via tiene un bug real de parseo de argumentos
# con valores tipo "X.Y.Z.W", ver CNDL0103 en el historial del proyecto).
$productWxsContent = Get-Content "packaging\wix\Product.wxs" -Raw
$replacement = 'Version="' + $productVersion + '"'
$productWxsContent = $productWxsContent -replace 'Version="0\.0\.0\.0"', $replacement
Set-Content -Path "$objDir\Product.generated.wxs" -Value $productWxsContent -Encoding utf8BOM -NoNewline

Write-Host "== 5) Compilando con candle.exe ==" -ForegroundColor Cyan
& $candle -dSourceDir="dist\AsistenteIA" -out "$objDir\" "$objDir\Product.generated.wxs" "packaging\wix\Files.wxs"

Write-Host "== 6) Enlazando con light.exe (genera el .msi final) ==" -ForegroundColor Cyan
& $light -out "dist\AsistenteIA-Setup.msi" "$objDir\Product.generated.wixobj" "$objDir\Files.wixobj"

Write-Host ""
Write-Host "Listo: dist\AsistenteIA-Setup.msi" -ForegroundColor Green
