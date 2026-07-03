# Map2Drone Database Setup Script
param(
    [string]$DbName = "map2drone",
    [string]$DbUser = "map2drone",
    [string]$DbPass = "map2drone"
)

Write-Host "=== Map2Drone Database Setup ===" -ForegroundColor Cyan

# Check if PostgreSQL is available
$psqlPath = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlPath) {
    Write-Host "ERROR: PostgreSQL (psql) not found. Install PostgreSQL 16+ with PostGIS." -ForegroundColor Red
    exit 1
}

Write-Host "Creating user: $DbUser" -ForegroundColor Yellow
& psql -U postgres -c "CREATE USER $DbUser WITH PASSWORD '$DbPass';" 2>$null

Write-Host "Creating database: $DbName" -ForegroundColor Yellow
& psql -U postgres -c "CREATE DATABASE $DbName OWNER $DbUser;" 2>$null

Write-Host "Enabling PostGIS extension" -ForegroundColor Yellow
& psql -U postgres -d $DbName -c "CREATE EXTENSION IF NOT EXISTS postgis;"
& psql -U postgres -d $DbName -c "CREATE EXTENSION IF NOT EXISTS postgis_topology;"
& psql -U postgres -d $DbName -c "CREATE EXTENSION IF NOT EXISTS uuid-ossp;"

Write-Host "Granting permissions" -ForegroundColor Yellow
& psql -U postgres -d $DbName -c "GRANT ALL ON SCHEMA public TO $DbUser;"

Write-Host "Running seed data..." -ForegroundColor Yellow
$scriptPath = Join-Path $PSScriptRoot "seed-data.sql"
if (Test-Path $scriptPath) {
    & psql -U postgres -d $DbName -f $scriptPath
}

Write-Host "=== Setup complete ===" -ForegroundColor Green
Write-Host "Database: $DbName" -ForegroundColor Green
Write-Host "User:     $DbUser" -ForegroundColor Green
Write-Host "Conn:     postgresql://${DbUser}:${DbPass}@localhost:5432/${DbName}" -ForegroundColor Green
