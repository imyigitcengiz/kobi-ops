# Proje kökünden çalıştırın: .\deploy\docker\build.ps1
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

if (-not (Test-Path '.env.docker')) {
    Copy-Item 'deploy\docker\.env.example' '.env.docker'
    Write-Host 'Olusturuldu: .env.docker — DJANGO_SECRET_KEY ve ALLOWED_HOSTS duzenleyin.' -ForegroundColor Yellow
}

Write-Host 'Docker imaji build ediliyor...' -ForegroundColor Cyan
docker compose build --no-cache
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host 'Container baslatiliyor...' -ForegroundColor Cyan
docker compose up -d
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ''
Write-Host 'Hazir: http://localhost:8000/giris/' -ForegroundColor Green
Write-Host 'Log: docker compose logs -f web'
