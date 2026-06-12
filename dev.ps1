# Start backend and frontend together
# Usage: .\dev.ps1

$root = $PSScriptRoot

# Backend — uvicorn with auto-reload
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$root\backend'; & '.\.venv\Scripts\uvicorn.exe' app.main:app --reload --port 8000"

# Frontend — Next.js dev server
Start-Process powershell -ArgumentList "-NoExit", "-Command",
    "cd '$root\frontend'; npm run dev"

Write-Host "Starting ByteOps..."
Write-Host "  Backend  → http://localhost:8000"
Write-Host "  Frontend → http://localhost:3000"
