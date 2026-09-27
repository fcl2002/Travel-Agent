Clear-Host

Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

Write-Host "Starting Travel Agent..."
python .\src\main.py