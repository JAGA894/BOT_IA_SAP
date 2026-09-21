# start_all.ps1 — Arranque completo del Bot CxC
# Ejecutar: powershell -ExecutionPolicy Bypass -File start_all.ps1
# Levanta: FastAPI + Ngrok + Node.js (WhatsApp) en orden correcto

$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $DIR

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BOT CxC — Arranque Completo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1) Matar procesos anteriores
Write-Host "`n[1/4] Deteniendo procesos anteriores..." -ForegroundColor Yellow
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "node*"   -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process -Name "ngrok"   -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
Write-Host "   OK" -ForegroundColor Green

# 2) Arrancar FastAPI en una nueva ventana
Write-Host "[2/4] Arrancando FastAPI (puerto 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$DIR'; .\venv\Scripts\python.exe -u bot_app.py" -WindowStyle Normal
Start-Sleep -Seconds 3

# Verificar que FastAPI responda
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "   FastAPI OK: $($r.Content)" -ForegroundColor Green
} catch {
    Write-Host "   ADVERTENCIA: FastAPI no responde aun (puede tardar). Continua..." -ForegroundColor DarkYellow
}

# 3) Arrancar Ngrok en una nueva ventana
Write-Host "[3/4] Arrancando Ngrok (https://approve-squid-contest.ngrok-free.dev)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ngrok http 8000" -WindowStyle Normal
Start-Sleep -Seconds 5

# Verificar tunel
try {
    $tunnels = Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -TimeoutSec 3
    $url = $tunnels.tunnels | Where-Object { $_.proto -eq 'https' } | Select-Object -First 1 -ExpandProperty public_url
    Write-Host "   Ngrok OK: $url" -ForegroundColor Green
} catch {
    Write-Host "   ADVERTENCIA: Ngrok aun iniciando..." -ForegroundColor DarkYellow
}

# 4) Arrancar Node.js (WhatsApp) en una nueva ventana
Write-Host "[4/4] Arrancando WhatsApp Client (Node.js)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$DIR'; node whatsapp_client.js" -WindowStyle Normal
Start-Sleep -Seconds 4

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  TODOS LOS SERVICIOS INICIADOS" -ForegroundColor Green
Write-Host "  FastAPI  → http://localhost:8000" -ForegroundColor White
Write-Host "  Ngrok    → https://approve-squid-contest.ngrok-free.dev" -ForegroundColor White
Write-Host "  WhatsApp → Escanea el QR si es primera vez" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nPresiona ENTER para salir de este script (los servicios siguen corriendo)."
Read-Host
