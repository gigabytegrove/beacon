#Requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$Root=Split-Path -Parent $PSScriptRoot
$Android=Join-Path $Root "clients\android"
$Dist=Join-Path $Root "dist"
$Expected=Join-Path $Android "app\build\outputs\apk\debug\Beacon-Android-0.7.0-debug.apk"
Write-Host "===== BEACON ANDROID APK BUILD =====" -ForegroundColor Cyan
if (!(Test-Path (Join-Path $Android "settings.gradle"))) { throw "Android project missing." }
if (!$env:ANDROID_HOME) {
  $candidate=Join-Path $env:LOCALAPPDATA "Android\Sdk"
  if (Test-Path $candidate) { $env:ANDROID_HOME=$candidate }
}
if (!$env:ANDROID_HOME -or !(Test-Path $env:ANDROID_HOME)) { throw "Android SDK not found. Install SDK 35 using Android Studio." }
if (!(Get-Command java.exe -ErrorAction SilentlyContinue)) {
  $jdk=Join-Path $env:ProgramFiles "Android\Android Studio\jbr\bin"
  if (Test-Path (Join-Path $jdk "java.exe")) { $env:Path="$jdk;$env:Path" }
  else { throw "JDK 17+ not found." }
}
$gradle=Get-Command gradle.bat -ErrorAction SilentlyContinue
if (!$gradle -and $env:GRADLE_HOME) {
  $candidate=Join-Path $env:GRADLE_HOME "bin\gradle.bat"
  if (Test-Path $candidate) { $gradle=Get-Item $candidate }
}
if (!$gradle) { throw "Gradle 8.9 not found; use Android Studio Build APK or install Gradle 8.9 on this build workstation." }
New-Item -ItemType Directory -Path $Dist -Force | Out-Null
Push-Location $Android
try {
  $gradleExe=if ($gradle -is [System.IO.FileInfo]) { $gradle.FullName } else { $gradle.Source }
  & $gradleExe --no-daemon :app:assembleDebug
  if ($LASTEXITCODE -ne 0) { throw "Android Gradle build failed." }
} finally { Pop-Location }
if (!(Test-Path $Expected) -or (Get-Item $Expected).Length -lt 102400) { throw "Expected debug APK missing." }
$Copy=Join-Path $Dist (Split-Path $Expected -Leaf)
Copy-Item $Expected $Copy -Force
$sum=(Get-FileHash -Algorithm SHA256 $Copy).Hash
"$sum  $(Split-Path $Copy -Leaf)" | Set-Content (Join-Path $Dist "Beacon-Android-0.7.0.sha256") -Encoding ASCII
Write-Host "SUCCESS: $Copy" -ForegroundColor Green
Write-Host "SHA256: $sum"
