# İmajı .tar olarak dışa aktarır (sunucuda: docker load -i ...)
$ErrorActionPreference = 'Stop'
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$ImageName = 'gy-dashboard-py:latest'
$OutFile = Join-Path $Root 'gy-dashboard-py-image.tar'

if (-not (docker image inspect $ImageName 2>$null)) {
    Write-Host 'Imaj yok, once build ediliyor...' -ForegroundColor Yellow
    docker compose build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Kaydediliyor: $OutFile" -ForegroundColor Cyan
docker save -o $OutFile $ImageName
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$sizeMb = [math]::Round((Get-Item $OutFile).Length / 1MB, 1)
Write-Host "Tamam ($sizeMb MB). Sunucuda: docker load -i gy-dashboard-py-image.tar" -ForegroundColor Green
Write-Host 'Ayrica sunucuya kopyalayin: docker-compose.yml, .env.docker'
