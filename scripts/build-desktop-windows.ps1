#Requires -Version 5.1
[CmdletBinding()]
param([switch]$SkipTests)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$Root=Split-Path -Parent $PSScriptRoot
$Module=Join-Path $Root "clients\desktop-go"
$Dist=Join-Path $Root "dist"
$Version="0.8.0"
$Output=Join-Path $Dist "Beacon-Windows-$Version.exe"
Write-Host "===== BEACON GO WINDOWS BUILD =====" -ForegroundColor Cyan
if (!(Test-Path (Join-Path $Module "go.mod"))) { throw "Beacon Go desktop source missing in $Module" }
$go=Get-Command go.exe -ErrorAction SilentlyContinue
if (!$go -and (Test-Path "$env:ProgramFiles\Go\bin\go.exe")) {
  $env:Path="$env:ProgramFiles\Go\bin;$env:Path"
  $go=Get-Command go.exe -ErrorAction SilentlyContinue
}
if (!$go) { throw "Go is required only to BUILD this executable. Install from https://go.dev/dl/ on the build workstation." }
$gcc=Get-Command gcc.exe -ErrorAction SilentlyContinue
foreach ($folder in @("C:\msys64\mingw64\bin","C:\tools\msys64\mingw64\bin","C:\msys64\ucrt64\bin")) {
  if (!$gcc -and (Test-Path (Join-Path $folder "gcc.exe"))) {
    $env:Path="$folder;$env:Path"
    $gcc=Get-Command gcc.exe -ErrorAction SilentlyContinue
  }
}
if (!$gcc) { throw "A MinGW-w64 GCC compiler is required on this build workstation. Install MSYS2 and its mingw-w64-x86_64-gcc package (https://www.msys2.org/)." }
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
$env:CGO_ENABLED="1"
$env:GOOS="windows"
$env:GOARCH="amd64"
Push-Location $Module
try {
  & go version
  & go mod tidy
  if ($LASTEXITCODE -ne 0) { throw "Dependency resolution failed." }
  if (!$SkipTests) {
    & go test ./internal/beacon
    if ($LASTEXITCODE -ne 0) { throw "Go API tests failed." }
  }
  & go build -trimpath '-ldflags=-s -w -H=windowsgui' -o $Output ./cmd/beacon
  if ($LASTEXITCODE -ne 0) { throw "Go/Fyne Windows GUI compilation failed." }
} finally { Pop-Location }
if (!(Test-Path $Output) -or (Get-Item $Output).Length -lt 1048576) { throw "Windows executable missing or too small." }
$hash=(Get-FileHash -Algorithm SHA256 $Output).Hash
"$hash  $(Split-Path $Output -Leaf)" | Set-Content (Join-Path $Dist "Beacon-Windows-$Version.sha256") -Encoding ASCII
Write-Host "SUCCESS: $Output" -ForegroundColor Green
Write-Host "SHA256: $hash"
Write-Host "End users need no Python, Go SDK, pip, or MinGW."
